from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_roles, require_staff
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import FormaPagamento, StatusPedidoInterline, StatusPoltrona, StatusRepasse, TipoOcupacao, UserRole
from app.models.interline import AcertoInterline, ConexaoInterline, PedidoInterline
from app.models.ocupacao_poltrona import OcupacaoPoltrona
from app.models.parada import Parada
from app.models.passagem import Passagem
from app.models.poltrona_viagem import PoltronaViagem
from app.models.rota import Rota
from app.models.usuario import Usuario
from app.models.viagem import Viagem
from app.routers.passagens import _criar_passagem_confirmada, _gerar_localizador_unico
from app.schemas.interline import (
    AcertoInterlineOut,
    ComprarInterlineRequest,
    CompraInterlineResponse,
    ConexaoInterlineOut,
    CriarConexaoInterlineRequest,
    OpcaoInterlineOut,
    PedidoInterlineOut,
    RotaParaConexaoOut,
)
from app.services.pagamento_provider import DadosCartao, modo_simulado, obter_configuracao_plataforma, obter_provider
from app.services.trecho import buscar_paradas_da_rota, calcular_preco_trecho, liberar_holds_expirados, status_da_poltrona_no_trecho

router = APIRouter(prefix="/interline", tags=["interline"])


def _conexao_para_out(db: Session, conexao: ConexaoInterline) -> ConexaoInterlineOut:
    rota_a = conexao.rota_perna_a or db.get(Rota, conexao.rota_perna_a_id)
    rota_b = conexao.rota_perna_b or db.get(Rota, conexao.rota_perna_b_id)
    empresa_a = conexao.empresa_a or db.get(Empresa, conexao.empresa_a_id)
    empresa_b = conexao.empresa_b or db.get(Empresa, conexao.empresa_b_id)
    return ConexaoInterlineOut(
        id=conexao.id,
        rota_perna_a_id=conexao.rota_perna_a_id,
        rota_perna_b_id=conexao.rota_perna_b_id,
        empresa_a_id=conexao.empresa_a_id,
        empresa_b_id=conexao.empresa_b_id,
        empresa_a_nome=empresa_a.nome if empresa_a else None,
        empresa_b_nome=empresa_b.nome if empresa_b else None,
        origem_a=rota_a.origem if rota_a else None,
        destino_a=rota_a.destino if rota_a else None,
        origem_b=rota_b.origem if rota_b else None,
        destino_b=rota_b.destino if rota_b else None,
        parada_conexao_nome=conexao.parada_conexao_nome,
        minutos_conexao_minima=conexao.minutos_conexao_minima,
        ativo=conexao.ativo,
        criado_em=conexao.criado_em,
    )


@router.get("/rotas-disponiveis", response_model=list[RotaParaConexaoOut])
def listar_rotas_disponiveis(
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Todas as rotas ativas de todas as empresas, pro super admin montar
    uma ConexaoInterline — `GET /rotas` normal é escopado por tenant."""
    rotas = (
        db.query(Rota)
        .options(joinedload(Rota.empresa))
        .filter(Rota.ativo.is_(True))
        .order_by(Rota.origem)
        .all()
    )
    return [
        RotaParaConexaoOut(id=r.id, empresa_id=r.tenant_id, empresa_nome=r.empresa.nome if r.empresa else "", origem=r.origem, destino=r.destino)
        for r in rotas
    ]


@router.post("/conexoes", response_model=ConexaoInterlineOut, status_code=status.HTTP_201_CREATED)
def criar_conexao(
    dados: CriarConexaoInterlineRequest,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Só o super admin cadastra conexões (v1 não tem fluxo de proposta
    entre empresas — ver decisão de escopo no plano)."""
    rota_a = db.get(Rota, dados.rota_perna_a_id)
    rota_b = db.get(Rota, dados.rota_perna_b_id)
    if not rota_a or not rota_b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rota não encontrada")
    if rota_a.tenant_id == rota_b.tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="As duas pernas precisam ser de empresas diferentes")

    conexao = ConexaoInterline(
        rota_perna_a_id=rota_a.id,
        rota_perna_b_id=rota_b.id,
        empresa_a_id=rota_a.tenant_id,
        empresa_b_id=rota_b.tenant_id,
        parada_conexao_nome=dados.parada_conexao_nome,
        minutos_conexao_minima=dados.minutos_conexao_minima,
    )
    db.add(conexao)
    db.commit()
    db.refresh(conexao)
    return _conexao_para_out(db, conexao)


@router.get("/conexoes", response_model=list[ConexaoInterlineOut])
def listar_conexoes(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    """Super admin vê todas; admin/funcionário de empresa vê só as que
    envolvem a própria empresa (somente leitura pra eles)."""
    query = db.query(ConexaoInterline).options(
        joinedload(ConexaoInterline.rota_perna_a),
        joinedload(ConexaoInterline.rota_perna_b),
        joinedload(ConexaoInterline.empresa_a),
        joinedload(ConexaoInterline.empresa_b),
    )
    if usuario_atual.role != UserRole.SUPER_ADMIN:
        query = query.filter(
            or_(ConexaoInterline.empresa_a_id == usuario_atual.tenant_id, ConexaoInterline.empresa_b_id == usuario_atual.tenant_id)
        )
    conexoes = query.order_by(ConexaoInterline.criado_em.desc()).all()
    return [_conexao_para_out(db, c) for c in conexoes]


def _buscar_conexao_super_admin(db: Session, conexao_id: int) -> ConexaoInterline:
    conexao = db.get(ConexaoInterline, conexao_id)
    if not conexao:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conexão não encontrada")
    return conexao


@router.patch("/conexoes/{conexao_id}/ativar", response_model=ConexaoInterlineOut)
def ativar_conexao(
    conexao_id: int,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    conexao = _buscar_conexao_super_admin(db, conexao_id)
    conexao.ativo = True
    db.commit()
    db.refresh(conexao)
    return _conexao_para_out(db, conexao)


@router.patch("/conexoes/{conexao_id}/desativar", response_model=ConexaoInterlineOut)
def desativar_conexao(
    conexao_id: int,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    conexao = _buscar_conexao_super_admin(db, conexao_id)
    conexao.ativo = False
    db.commit()
    db.refresh(conexao)
    return _conexao_para_out(db, conexao)


@router.get("/buscar", response_model=list[OpcaoInterlineOut])
def buscar_interline(
    origem: str,
    destino: str,
    data: date,
    db: Session = Depends(get_db),
):
    """Sem autenticação — igual à busca normal da loja. V1 não faz busca de
    grafo geral: só resolve pares de viagem dentro de uma ConexaoInterline
    já cadastrada, cuja Rota A comece em `origem` e Rota B termine em
    `destino` (comparação simples de texto, mesmo padrão de Rota.origem/
    destino usado no resto do sistema)."""
    conexoes = (
        db.query(ConexaoInterline)
        .options(
            joinedload(ConexaoInterline.rota_perna_a),
            joinedload(ConexaoInterline.rota_perna_b),
            joinedload(ConexaoInterline.empresa_a),
            joinedload(ConexaoInterline.empresa_b),
        )
        .filter(ConexaoInterline.ativo.is_(True))
        .all()
    )

    origem_normalizada = origem.strip().lower()
    destino_normalizado = destino.strip().lower()
    inicio_dia = datetime.combine(data, datetime.min.time())
    fim_dia = datetime.combine(data, datetime.max.time())

    opcoes: list[OpcaoInterlineOut] = []
    for conexao in conexoes:
        if conexao.rota_perna_a.origem.strip().lower() != origem_normalizada:
            continue
        if conexao.rota_perna_b.destino.strip().lower() != destino_normalizado:
            continue

        paradas_a = buscar_paradas_da_rota(db, conexao.rota_perna_a_id)
        paradas_b = buscar_paradas_da_rota(db, conexao.rota_perna_b_id)
        if not paradas_a or not paradas_b:
            continue

        viagens_a = (
            db.query(Viagem)
            .filter(
                Viagem.rota_id == conexao.rota_perna_a_id,
                Viagem.ativo.is_(True),
                Viagem.data_hora_partida >= inicio_dia,
                Viagem.data_hora_partida <= fim_dia,
            )
            .all()
        )
        if not viagens_a:
            continue
        viagens_b = (
            db.query(Viagem)
            .filter(
                Viagem.rota_id == conexao.rota_perna_b_id,
                Viagem.ativo.is_(True),
                Viagem.data_hora_partida >= inicio_dia,
                Viagem.data_hora_partida <= fim_dia + timedelta(days=1),
            )
            .all()
        )

        for viagem_a in viagens_a:
            limite = viagem_a.data_hora_partida + timedelta(minutes=conexao.minutos_conexao_minima)
            for viagem_b in viagens_b:
                if viagem_b.data_hora_partida < limite:
                    continue
                valor_a = calcular_preco_trecho(paradas_a, paradas_a[0].ordem, paradas_a[-1].ordem, viagem_a.preco)
                valor_b = calcular_preco_trecho(paradas_b, paradas_b[0].ordem, paradas_b[-1].ordem, viagem_b.preco)
                opcoes.append(
                    OpcaoInterlineOut(
                        conexao_id=conexao.id,
                        parada_conexao_nome=conexao.parada_conexao_nome,
                        empresa_a_nome=conexao.empresa_a.nome,
                        empresa_b_nome=conexao.empresa_b.nome,
                        viagem_perna_a_id=viagem_a.id,
                        viagem_perna_b_id=viagem_b.id,
                        data_hora_partida_a=viagem_a.data_hora_partida,
                        data_hora_partida_b=viagem_b.data_hora_partida,
                        valor_perna_a=valor_a,
                        valor_perna_b=valor_b,
                        valor_total=round(valor_a + valor_b, 2),
                    )
                )

    opcoes.sort(key=lambda o: o.data_hora_partida_a)
    return opcoes


def _pedido_para_out(pedido: PedidoInterline, *, pagamento_simulado: bool) -> PedidoInterlineOut:
    return PedidoInterlineOut(
        id=pedido.id,
        conexao_id=pedido.conexao_id,
        status=pedido.status,
        valor_perna_a=float(pedido.valor_perna_a),
        valor_perna_b=float(pedido.valor_perna_b),
        valor_total=float(pedido.valor_total),
        passagem_perna_a_id=pedido.passagem_perna_a_id,
        passagem_perna_b_id=pedido.passagem_perna_b_id,
        pix_copia_cola=pedido.pix_copia_cola,
        pix_expira_em=pedido.pix_expira_em,
        criado_em=pedido.criado_em,
        pagamento_simulado=pagamento_simulado,
    )


def _criar_passagens_do_pedido_interline(db: Session, pedido: PedidoInterline, gateway_ref_perna_a: str) -> tuple[Passagem, Passagem]:
    """Cria as duas Passagens (uma por empresa) a partir de um
    PedidoInterline já com todos os dados da compra salvos, e registra o
    AcertoInterline da perna B (o cliente já pagou o valor total pra
    empresa vendedora — a perna B não passa pelo gateway de novo). Usado
    tanto na aprovação na hora (cartão/dinheiro) quanto na confirmação de
    um Pix pendente (simulada ou via webhook do Mercado Pago)."""
    conexao = db.get(ConexaoInterline, pedido.conexao_id)
    viagem_a = db.get(Viagem, pedido.viagem_perna_a_id)
    poltrona_a = db.get(PoltronaViagem, pedido.poltrona_perna_a_id)
    parada_origem_a = db.get(Parada, pedido.parada_origem_a_id)
    parada_destino_a = db.get(Parada, pedido.parada_destino_a_id)
    viagem_b = db.get(Viagem, pedido.viagem_perna_b_id)
    poltrona_b = db.get(PoltronaViagem, pedido.poltrona_perna_b_id)
    parada_origem_b = db.get(Parada, pedido.parada_origem_b_id)
    parada_destino_b = db.get(Parada, pedido.parada_destino_b_id)

    usuario_do_pedido = db.get(Usuario, pedido.usuario_id)
    cliente_usuario_id = usuario_do_pedido.id if usuario_do_pedido and usuario_do_pedido.role == UserRole.CLIENTE else None
    vendido_por_usuario_id = (
        usuario_do_pedido.id
        if usuario_do_pedido and usuario_do_pedido.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN)
        else None
    )

    def _hold_pendente(poltrona_id: int, parada_origem: Parada, parada_destino: Parada) -> OcupacaoPoltrona | None:
        return (
            db.query(OcupacaoPoltrona)
            .filter(
                OcupacaoPoltrona.poltrona_viagem_id == poltrona_id,
                OcupacaoPoltrona.tipo == TipoOcupacao.HOLD,
                OcupacaoPoltrona.parada_origem_ordem == parada_origem.ordem,
                OcupacaoPoltrona.parada_destino_ordem == parada_destino.ordem,
            )
            .first()
        )

    passagem_a = _criar_passagem_confirmada(
        db,
        viagem=viagem_a,
        poltrona=poltrona_a,
        parada_origem=parada_origem_a,
        parada_destino=parada_destino_a,
        localizador=_gerar_localizador_unico(db),
        cliente_nome=pedido.cliente_nome,
        cliente_documento=pedido.cliente_documento,
        cliente_telefone=pedido.cliente_telefone,
        tipo_documento=pedido.tipo_documento,
        categoria_passageiro=pedido.categoria_passageiro,
        cliente_usuario_id=cliente_usuario_id,
        vendido_por_usuario_id=vendido_por_usuario_id,
        preco_final=float(pedido.valor_perna_a),
        forma_pagamento=pedido.forma_pagamento,
        gateway_ref=gateway_ref_perna_a,
        hold_para_remover=_hold_pendente(poltrona_a.id, parada_origem_a, parada_destino_a),
        usuario_para_notificar=usuario_do_pedido,
    )
    passagem_b = _criar_passagem_confirmada(
        db,
        viagem=viagem_b,
        poltrona=poltrona_b,
        parada_origem=parada_origem_b,
        parada_destino=parada_destino_b,
        localizador=_gerar_localizador_unico(db),
        cliente_nome=pedido.cliente_nome,
        cliente_documento=pedido.cliente_documento,
        cliente_telefone=pedido.cliente_telefone,
        tipo_documento=pedido.tipo_documento,
        categoria_passageiro=pedido.categoria_passageiro,
        cliente_usuario_id=cliente_usuario_id,
        vendido_por_usuario_id=vendido_por_usuario_id,
        preco_final=float(pedido.valor_perna_b),
        forma_pagamento=pedido.forma_pagamento,
        gateway_ref=f"INTERLINE-{pedido.id}",
        hold_para_remover=_hold_pendente(poltrona_b.id, parada_origem_b, parada_destino_b),
        usuario_para_notificar=None,  # evita notificar o cliente duas vezes pela mesma compra
    )

    pedido.passagem_perna_a_id = passagem_a.id
    pedido.passagem_perna_b_id = passagem_b.id
    pedido.status = StatusPedidoInterline.CONFIRMADO

    db.add(
        AcertoInterline(
            pedido_interline_id=pedido.id,
            empresa_devedora_id=conexao.empresa_a_id,
            empresa_credora_id=conexao.empresa_b_id,
            valor_devido=pedido.valor_perna_b,
        )
    )
    db.commit()

    return passagem_a, passagem_b


@router.post("/pedidos", response_model=CompraInterlineResponse, status_code=status.HTTP_201_CREATED)
def comprar_interline(
    dados: ComprarInterlineRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    """Compra combinada das duas pernas. A empresa da perna A é sempre
    quem cobra o cliente (v1: é ela quem o cliente encontrou primeiro,
    normalmente pela própria loja dela) — a perna B não é cobrada de novo,
    vira um AcertoInterline a receber pra empresa B."""
    conexao = db.get(ConexaoInterline, dados.conexao_id)
    if not conexao or not conexao.ativo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conexão interline não encontrada")

    viagem_a = db.get(Viagem, dados.viagem_perna_a_id)
    if not viagem_a or viagem_a.rota_id != conexao.rota_perna_a_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem da perna A inválida para esta conexão")
    viagem_b = db.get(Viagem, dados.viagem_perna_b_id)
    if not viagem_b or viagem_b.rota_id != conexao.rota_perna_b_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem da perna B inválida para esta conexão")

    poltrona_a = db.get(PoltronaViagem, dados.poltrona_perna_a_id)
    if not poltrona_a or poltrona_a.viagem_id != viagem_a.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poltrona da perna A não encontrada")
    poltrona_b = db.get(PoltronaViagem, dados.poltrona_perna_b_id)
    if not poltrona_b or poltrona_b.viagem_id != viagem_b.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poltrona da perna B não encontrada")

    paradas_a = buscar_paradas_da_rota(db, viagem_a.rota_id)
    paradas_b = buscar_paradas_da_rota(db, viagem_b.rota_id)
    if not paradas_a or not paradas_b:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rota sem paradas cadastradas")
    parada_origem_a, parada_destino_a = paradas_a[0], paradas_a[-1]
    parada_origem_b, parada_destino_b = paradas_b[0], paradas_b[-1]

    liberar_holds_expirados(db, [poltrona_a.id, poltrona_b.id])

    ocupacoes_a = db.query(OcupacaoPoltrona).filter(OcupacaoPoltrona.poltrona_viagem_id == poltrona_a.id).all()
    status_a, conflito_a = status_da_poltrona_no_trecho(ocupacoes_a, parada_origem_a.ordem, parada_destino_a.ordem)
    ocupacoes_b = db.query(OcupacaoPoltrona).filter(OcupacaoPoltrona.poltrona_viagem_id == poltrona_b.id).all()
    status_b, conflito_b = status_da_poltrona_no_trecho(ocupacoes_b, parada_origem_b.ordem, parada_destino_b.ordem)

    is_staff = usuario_atual.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN)

    def _disponivel(status_pv: StatusPoltrona, conflito: OcupacaoPoltrona | None) -> bool:
        return status_pv == StatusPoltrona.LIVRE or (
            status_pv == StatusPoltrona.HOLD and conflito is not None and (is_staff or conflito.usuario_id == usuario_atual.id)
        )

    if not _disponivel(status_a, conflito_a):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Poltrona da perna A não está disponível")
    if not _disponivel(status_b, conflito_b):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Poltrona da perna B não está disponível")

    valor_perna_a = round(
        calcular_preco_trecho(paradas_a, parada_origem_a.ordem, parada_destino_a.ordem, viagem_a.preco)
        * float(poltrona_a.poltrona_onibus.multiplicador_preco),
        2,
    )
    valor_perna_b = round(
        calcular_preco_trecho(paradas_b, parada_origem_b.ordem, parada_destino_b.ordem, viagem_b.preco)
        * float(poltrona_b.poltrona_onibus.multiplicador_preco),
        2,
    )
    valor_total = round(valor_perna_a + valor_perna_b, 2)

    empresa_vendedora = db.get(Empresa, conexao.empresa_a_id)
    config_plataforma = obter_configuracao_plataforma(db)

    dados_cartao = None
    if dados.forma_pagamento == FormaPagamento.CARTAO and dados.mp_token:
        dados_cartao = DadosCartao(
            token=dados.mp_token,
            payment_method_id=dados.mp_payment_method_id or "",
            installments=dados.mp_installments or 1,
            payer_email=dados.mp_payer_email,
            payer_documento=dados.cliente_documento,
        )

    try:
        resultado_cobranca = obter_provider(
            empresa_vendedora, taxa_transacao_percentual=config_plataforma.taxa_transacao_percentual
        ).cobrar(
            forma_pagamento=dados.forma_pagamento,
            valor=valor_total,
            referencia_pedido=f"interline-{conexao.id}-{viagem_a.id}-{viagem_b.id}",
            dados_cartao=dados_cartao,
        )
    except ValueError as erro:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(erro))

    if resultado_cobranca.status == "recusado":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pagamento recusado pelo Mercado Pago. Tente outro cartão.")

    hold_a = conflito_a if (conflito_a and conflito_a.tipo == TipoOcupacao.HOLD) else None
    hold_b = conflito_b if (conflito_b and conflito_b.tipo == TipoOcupacao.HOLD) else None

    if resultado_cobranca.status == "pendente":
        # Pix ainda não caiu: segura as duas poltronas até a confirmação
        # (simulada ou webhook) em vez de vender agora — mesmo padrão de
        # vender_passagem (app/routers/passagens.py), só que nas duas pernas.
        if hold_a is not None:
            hold_a.expira_em = resultado_cobranca.pix_expira_em
            if hold_a.usuario_id is None:
                hold_a.usuario_id = usuario_atual.id
        else:
            db.add(
                OcupacaoPoltrona(
                    poltrona_viagem_id=poltrona_a.id,
                    tipo=TipoOcupacao.HOLD,
                    parada_origem_ordem=parada_origem_a.ordem,
                    parada_destino_ordem=parada_destino_a.ordem,
                    usuario_id=usuario_atual.id,
                    expira_em=resultado_cobranca.pix_expira_em,
                )
            )
        if hold_b is not None:
            hold_b.expira_em = resultado_cobranca.pix_expira_em
            if hold_b.usuario_id is None:
                hold_b.usuario_id = usuario_atual.id
        else:
            db.add(
                OcupacaoPoltrona(
                    poltrona_viagem_id=poltrona_b.id,
                    tipo=TipoOcupacao.HOLD,
                    parada_origem_ordem=parada_origem_b.ordem,
                    parada_destino_ordem=parada_destino_b.ordem,
                    usuario_id=usuario_atual.id,
                    expira_em=resultado_cobranca.pix_expira_em,
                )
            )

        pedido = PedidoInterline(
            conexao_id=conexao.id,
            usuario_id=usuario_atual.id,
            cliente_nome=dados.cliente_nome,
            cliente_documento=dados.cliente_documento,
            cliente_telefone=dados.cliente_telefone,
            tipo_documento=dados.tipo_documento,
            categoria_passageiro=dados.categoria_passageiro,
            forma_pagamento=dados.forma_pagamento,
            viagem_perna_a_id=viagem_a.id,
            poltrona_perna_a_id=poltrona_a.id,
            parada_origem_a_id=parada_origem_a.id,
            parada_destino_a_id=parada_destino_a.id,
            viagem_perna_b_id=viagem_b.id,
            poltrona_perna_b_id=poltrona_b.id,
            parada_origem_b_id=parada_origem_b.id,
            parada_destino_b_id=parada_destino_b.id,
            valor_perna_a=valor_perna_a,
            valor_perna_b=valor_perna_b,
            valor_total=valor_total,
            status=StatusPedidoInterline.PENDENTE_PAGAMENTO,
            pix_copia_cola=resultado_cobranca.pix_copia_cola,
            pix_expira_em=resultado_cobranca.pix_expira_em,
            gateway_ref=resultado_cobranca.gateway_ref,
        )
        db.add(pedido)
        db.commit()
        db.refresh(pedido)
        simulado = modo_simulado(empresa=empresa_vendedora)
        return CompraInterlineResponse(pedido_interline=_pedido_para_out(pedido, pagamento_simulado=simulado))

    pedido = PedidoInterline(
        conexao_id=conexao.id,
        usuario_id=usuario_atual.id,
        cliente_nome=dados.cliente_nome,
        cliente_documento=dados.cliente_documento,
        cliente_telefone=dados.cliente_telefone,
        tipo_documento=dados.tipo_documento,
        categoria_passageiro=dados.categoria_passageiro,
        forma_pagamento=dados.forma_pagamento,
        viagem_perna_a_id=viagem_a.id,
        poltrona_perna_a_id=poltrona_a.id,
        parada_origem_a_id=parada_origem_a.id,
        parada_destino_a_id=parada_destino_a.id,
        viagem_perna_b_id=viagem_b.id,
        poltrona_perna_b_id=poltrona_b.id,
        parada_origem_b_id=parada_origem_b.id,
        parada_destino_b_id=parada_destino_b.id,
        valor_perna_a=valor_perna_a,
        valor_perna_b=valor_perna_b,
        valor_total=valor_total,
        status=StatusPedidoInterline.PENDENTE_PAGAMENTO,
    )
    db.add(pedido)
    db.flush()

    passagem_a, passagem_b = _criar_passagens_do_pedido_interline(db, pedido, gateway_ref_perna_a=resultado_cobranca.gateway_ref)

    return CompraInterlineResponse(
        passagem_perna_a_id=passagem_a.id,
        passagem_perna_b_id=passagem_b.id,
        localizador_perna_a=passagem_a.localizador,
        localizador_perna_b=passagem_b.localizador,
    )


def _buscar_pedido_do_usuario(db: Session, pedido_id: int, usuario_atual: Usuario) -> PedidoInterline:
    pedido = db.get(PedidoInterline, pedido_id)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido interline não encontrado")
    conexao = db.get(ConexaoInterline, pedido.conexao_id)
    eh_dono = pedido.usuario_id == usuario_atual.id
    eh_staff_envolvido = usuario_atual.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN) and (
        usuario_atual.role == UserRole.SUPER_ADMIN
        or usuario_atual.tenant_id in (conexao.empresa_a_id, conexao.empresa_b_id)
    )
    if not eh_dono and not eh_staff_envolvido:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")

    if pedido.status == StatusPedidoInterline.PENDENTE_PAGAMENTO and pedido.pix_expira_em and pedido.pix_expira_em < datetime.utcnow():
        pedido.status = StatusPedidoInterline.CANCELADO
        db.commit()
        db.refresh(pedido)
    return pedido


@router.get("/pedidos/{pedido_id}", response_model=PedidoInterlineOut)
def consultar_pedido_interline(
    pedido_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    pedido = _buscar_pedido_do_usuario(db, pedido_id, usuario_atual)
    conexao = db.get(ConexaoInterline, pedido.conexao_id)
    simulado = modo_simulado(empresa=db.get(Empresa, conexao.empresa_a_id))
    return _pedido_para_out(pedido, pagamento_simulado=simulado)


@router.post("/pedidos/{pedido_id}/confirmar-simulado", response_model=CompraInterlineResponse)
def confirmar_pedido_interline_simulado(
    pedido_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    """Simula o webhook que um gateway real chamaria quando o Pix cai —
    mesmo espírito de /pedidos-pagamento/{id}/confirmar-simulado, só que
    fecha as duas pernas de uma vez. Só existe em modo simulado."""
    pedido = _buscar_pedido_do_usuario(db, pedido_id, usuario_atual)
    conexao = db.get(ConexaoInterline, pedido.conexao_id)
    empresa_vendedora = db.get(Empresa, conexao.empresa_a_id)

    if not modo_simulado(empresa=empresa_vendedora):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmação manual desabilitada: um gateway de pagamento real está configurado.",
        )
    if pedido.status == StatusPedidoInterline.CONFIRMADO:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pedido já confirmado")
    if pedido.status != StatusPedidoInterline.PENDENTE_PAGAMENTO:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pedido não está mais pendente (expirado ou cancelado)")

    passagem_a, passagem_b = _criar_passagens_do_pedido_interline(db, pedido, gateway_ref_perna_a=f"SIMULADO-{pedido.id}")
    return CompraInterlineResponse(
        passagem_perna_a_id=passagem_a.id,
        passagem_perna_b_id=passagem_b.id,
        localizador_perna_a=passagem_a.localizador,
        localizador_perna_b=passagem_b.localizador,
    )


@router.get("/acertos", response_model=list[AcertoInterlineOut])
def listar_acertos_interline(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    """Dívidas/créditos entre empresas — devendo (a empresa vendeu e deve
    a outra) ou a receber (a empresa operou a perna B e tem a receber)."""
    query = db.query(AcertoInterline).options(
        joinedload(AcertoInterline.empresa_devedora), joinedload(AcertoInterline.empresa_credora)
    )
    if usuario_atual.role != UserRole.SUPER_ADMIN:
        query = query.filter(
            or_(AcertoInterline.empresa_devedora_id == usuario_atual.tenant_id, AcertoInterline.empresa_credora_id == usuario_atual.tenant_id)
        )
    acertos = query.order_by(AcertoInterline.criado_em.desc()).all()
    return [
        AcertoInterlineOut(
            id=a.id,
            pedido_interline_id=a.pedido_interline_id,
            empresa_devedora_id=a.empresa_devedora_id,
            empresa_credora_id=a.empresa_credora_id,
            empresa_devedora_nome=a.empresa_devedora.nome if a.empresa_devedora else None,
            empresa_credora_nome=a.empresa_credora.nome if a.empresa_credora else None,
            valor_devido=float(a.valor_devido),
            status=a.status,
            criado_em=a.criado_em,
            pago_em=a.pago_em,
        )
        for a in acertos
    ]


@router.patch("/acertos/{acerto_id}/marcar-pago", response_model=AcertoInterlineOut)
def marcar_acerto_interline_pago(
    acerto_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    """Só a empresa credora (quem tem a receber) marca como recebido —
    espelha marcar_repasse_pago (app/routers/parceiros.py)."""
    acerto = db.get(AcertoInterline, acerto_id)
    if not acerto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acerto não encontrado")
    if usuario_atual.role != UserRole.SUPER_ADMIN and usuario_atual.tenant_id != acerto.empresa_credora_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Só a empresa credora pode marcar este acerto como pago")
    if acerto.status == StatusRepasse.PAGO:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Acerto já marcado como pago")

    acerto.status = StatusRepasse.PAGO
    acerto.pago_em = datetime.utcnow()
    db.commit()
    db.refresh(acerto)
    return AcertoInterlineOut(
        id=acerto.id,
        pedido_interline_id=acerto.pedido_interline_id,
        empresa_devedora_id=acerto.empresa_devedora_id,
        empresa_credora_id=acerto.empresa_credora_id,
        empresa_devedora_nome=acerto.empresa_devedora.nome if acerto.empresa_devedora else None,
        empresa_credora_nome=acerto.empresa_credora.nome if acerto.empresa_credora else None,
        valor_devido=float(acerto.valor_devido),
        status=acerto.status,
        criado_em=acerto.criado_em,
        pago_em=acerto.pago_em,
    )
