from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_staff
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import FormaPagamento, StatusPassagem, StatusPedidoPagamento, StatusPoltrona, UserRole
from app.models.evento import AssentoSessao, Ingresso, PedidoIngressoPendente, Sessao
from app.models.usuario import Usuario
from app.schemas.ingresso import (
    ComprarIngressoRequest,
    CompraIngressoResponse,
    IngressoOut,
    PedidoIngressoOut,
    ReembolsarIngressoRequest,
    ReembolsoIngressoOut,
)
from app.services.auditoria import registrar as registrar_auditoria
from app.services.codigo import gerar_localizador
from app.services.pagamento_provider import DadosCartao, modo_simulado, obter_configuracao_plataforma, obter_provider

router = APIRouter(tags=["ingressos"])


def _gerar_codigo_unico_ingresso(db: Session) -> str:
    codigo = gerar_localizador()
    while db.query(Ingresso).filter(Ingresso.codigo == codigo).first():
        codigo = gerar_localizador()
    return codigo


def _ingresso_para_out(ingresso: Ingresso) -> IngressoOut:
    sessao = ingresso.sessao
    return IngressoOut(
        id=ingresso.id,
        sessao_id=ingresso.sessao_id,
        assento_sessao_id=ingresso.assento_sessao_id,
        cliente_nome=ingresso.cliente_nome,
        cliente_documento=ingresso.cliente_documento,
        preco=float(ingresso.preco),
        forma_pagamento=ingresso.forma_pagamento,
        status=ingresso.status,
        codigo=ingresso.codigo,
        criado_em=ingresso.criado_em,
        checkin_em=ingresso.checkin_em,
        valor_reembolsado=float(ingresso.valor_reembolsado) if ingresso.valor_reembolsado else None,
        motivo_reembolso=ingresso.motivo_reembolso,
        reembolsado_em=ingresso.reembolsado_em,
        nome_evento=sessao.nome_evento if sessao else None,
        local_nome=sessao.local.nome if sessao and sessao.local else None,
        data_hora=sessao.data_hora if sessao else None,
        numero_assento=ingresso.assento_sessao.assento_local.numero if ingresso.assento_sessao else None,
    )


def _pedido_para_out(pedido: PedidoIngressoPendente, *, pagamento_simulado: bool) -> PedidoIngressoOut:
    return PedidoIngressoOut(
        id=pedido.id,
        sessao_id=pedido.sessao_id,
        status=pedido.status,
        valor=float(pedido.valor),
        forma_pagamento=pedido.forma_pagamento,
        pix_copia_cola=pedido.pix_copia_cola,
        expira_em=pedido.expira_em,
        criado_em=pedido.criado_em,
        ingresso_id=pedido.ingresso_id,
        pagamento_simulado=pagamento_simulado,
    )


def _criar_ingresso_confirmado(
    db: Session,
    *,
    sessao: Sessao,
    assento: AssentoSessao,
    codigo: str,
    cliente_nome: str,
    cliente_documento: str,
    cliente_usuario_id: int | None,
    vendido_por_usuario_id: int | None,
    preco_final: float,
    forma_pagamento: FormaPagamento,
    gateway_ref: str | None,
    usuario_para_auditoria: Usuario | None,
) -> Ingresso:
    ingresso = Ingresso(
        tenant_id=sessao.tenant_id,
        sessao_id=sessao.id,
        assento_sessao_id=assento.id,
        cliente_usuario_id=cliente_usuario_id,
        cliente_nome=cliente_nome,
        cliente_documento=cliente_documento,
        vendido_por_usuario_id=vendido_por_usuario_id,
        preco=preco_final,
        forma_pagamento=forma_pagamento,
        gateway_ref=gateway_ref,
        status=StatusPassagem.CONFIRMADA,
        codigo=codigo,
    )
    db.add(ingresso)
    db.flush()

    assento.status = StatusPoltrona.VENDIDA
    assento.hold_usuario_id = None
    assento.hold_expira_em = None
    assento.ingresso_id = ingresso.id

    registrar_auditoria(
        db,
        usuario=usuario_para_auditoria,
        acao="venda_ingresso",
        entidade_tipo="ingresso",
        entidade_id=ingresso.id,
        detalhes=f"Código {codigo}, assento {assento.assento_local.numero}, sessão {sessao.nome_evento}, R$ {preco_final}",
        tenant_id=sessao.tenant_id,
    )

    db.commit()
    db.refresh(ingresso)
    return ingresso


@router.post("/sessoes/{sessao_id}/ingressos", response_model=CompraIngressoResponse, status_code=status.HTTP_201_CREATED)
def comprar_ingresso(
    sessao_id: int,
    dados: ComprarIngressoRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    sessao = db.get(Sessao, sessao_id)
    if not sessao or not sessao.ativo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessão não encontrada")

    assento = db.get(AssentoSessao, dados.assento_sessao_id)
    if not assento or assento.sessao_id != sessao_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assento não encontrado")

    is_staff = usuario_atual.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN)
    cliente_usuario_id = usuario_atual.id if usuario_atual.role == UserRole.CLIENTE else None

    if assento.status == StatusPoltrona.HOLD and assento.hold_expira_em and assento.hold_expira_em < datetime.utcnow():
        assento.status = StatusPoltrona.LIVRE
        assento.hold_usuario_id = None
        assento.hold_expira_em = None

    pode_confirmar = assento.status == StatusPoltrona.LIVRE or (
        assento.status == StatusPoltrona.HOLD and (is_staff or assento.hold_usuario_id == usuario_atual.id)
    )
    if not pode_confirmar:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Assento não está disponível")

    preco_final = round(float(sessao.preco) * float(assento.assento_local.multiplicador_preco), 2)

    empresa = db.get(Empresa, sessao.tenant_id)
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
            empresa, taxa_transacao_percentual=config_plataforma.taxa_transacao_percentual
        ).cobrar(
            forma_pagamento=dados.forma_pagamento,
            valor=preco_final,
            referencia_pedido=f"sessao-{sessao_id}-assento-{assento.id}",
            dados_cartao=dados_cartao,
        )
    except ValueError as erro:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(erro))

    if resultado_cobranca.status == "recusado":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pagamento recusado pelo Mercado Pago. Tente outro cartão.")

    if resultado_cobranca.status == "pendente":
        assento.status = StatusPoltrona.HOLD
        assento.hold_usuario_id = usuario_atual.id
        assento.hold_expira_em = resultado_cobranca.pix_expira_em

        pedido = PedidoIngressoPendente(
            tenant_id=sessao.tenant_id,
            sessao_id=sessao_id,
            assento_sessao_id=assento.id,
            usuario_id=usuario_atual.id,
            cliente_nome=dados.cliente_nome,
            cliente_documento=dados.cliente_documento,
            forma_pagamento=dados.forma_pagamento,
            valor=preco_final,
            pix_copia_cola=resultado_cobranca.pix_copia_cola,
            gateway_ref=resultado_cobranca.gateway_ref,
            expira_em=resultado_cobranca.pix_expira_em,
        )
        db.add(pedido)
        db.commit()
        db.refresh(pedido)
        simulado = modo_simulado(empresa=empresa)
        return CompraIngressoResponse(pedido_ingresso=_pedido_para_out(pedido, pagamento_simulado=simulado))

    ingresso = _criar_ingresso_confirmado(
        db,
        sessao=sessao,
        assento=assento,
        codigo=_gerar_codigo_unico_ingresso(db),
        cliente_nome=dados.cliente_nome,
        cliente_documento=dados.cliente_documento,
        cliente_usuario_id=cliente_usuario_id,
        vendido_por_usuario_id=usuario_atual.id if is_staff else None,
        preco_final=preco_final,
        forma_pagamento=dados.forma_pagamento,
        gateway_ref=resultado_cobranca.gateway_ref,
        usuario_para_auditoria=usuario_atual,
    )
    return CompraIngressoResponse(ingresso=_ingresso_para_out(ingresso))


def confirmar_pedido_ingresso(db: Session, pedido: PedidoIngressoPendente, gateway_ref: str) -> Ingresso:
    """Cria o ingresso de verdade e fecha o pedido — chamado tanto pelo
    endpoint de confirmação manual/simulada quanto pelo webhook do
    Mercado Pago (app/routers/webhooks.py), mesmo padrão de
    confirmar_pedido_pagamento (app/routers/pedidos_pagamento.py)."""
    if pedido.status == StatusPedidoPagamento.CONFIRMADO:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pedido já confirmado")
    if pedido.status != StatusPedidoPagamento.PENDENTE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pedido não está mais pendente (expirado ou cancelado)")

    sessao = db.get(Sessao, pedido.sessao_id)
    assento = db.get(AssentoSessao, pedido.assento_sessao_id)
    if not sessao or not assento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessão ou assento não encontrado")

    usuario_do_pedido = db.get(Usuario, pedido.usuario_id)
    cliente_usuario_id = usuario_do_pedido.id if usuario_do_pedido and usuario_do_pedido.role == UserRole.CLIENTE else None
    vendido_por_usuario_id = (
        usuario_do_pedido.id
        if usuario_do_pedido and usuario_do_pedido.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN)
        else None
    )

    ingresso = _criar_ingresso_confirmado(
        db,
        sessao=sessao,
        assento=assento,
        codigo=_gerar_codigo_unico_ingresso(db),
        cliente_nome=pedido.cliente_nome,
        cliente_documento=pedido.cliente_documento,
        cliente_usuario_id=cliente_usuario_id,
        vendido_por_usuario_id=vendido_por_usuario_id,
        preco_final=float(pedido.valor),
        forma_pagamento=pedido.forma_pagamento,
        gateway_ref=gateway_ref,
        usuario_para_auditoria=usuario_do_pedido,
    )

    pedido.status = StatusPedidoPagamento.CONFIRMADO
    pedido.ingresso_id = ingresso.id
    db.commit()

    return ingresso


def _buscar_pedido_do_usuario(db: Session, pedido_id: int, usuario_atual: Usuario) -> PedidoIngressoPendente:
    pedido = db.get(PedidoIngressoPendente, pedido_id)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido de ingresso não encontrado")
    eh_dono = pedido.usuario_id == usuario_atual.id
    eh_staff_da_empresa = (
        usuario_atual.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN)
        and usuario_atual.tenant_id == pedido.tenant_id
    )
    if not eh_dono and not eh_staff_da_empresa:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")

    if pedido.status == StatusPedidoPagamento.PENDENTE and pedido.expira_em < datetime.utcnow():
        pedido.status = StatusPedidoPagamento.EXPIRADO
        db.commit()
        db.refresh(pedido)
    return pedido


@router.get("/pedidos-ingresso/{pedido_id}", response_model=PedidoIngressoOut)
def consultar_pedido_ingresso(
    pedido_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    pedido = _buscar_pedido_do_usuario(db, pedido_id, usuario_atual)
    empresa = db.get(Empresa, pedido.tenant_id)
    return _pedido_para_out(pedido, pagamento_simulado=modo_simulado(empresa=empresa))


@router.post("/pedidos-ingresso/{pedido_id}/confirmar-simulado", response_model=CompraIngressoResponse)
def confirmar_pedido_ingresso_simulado(
    pedido_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    """Simula o webhook que um gateway real chamaria quando o Pix cai —
    só existe em modo simulado (ver modo_simulado())."""
    pedido = _buscar_pedido_do_usuario(db, pedido_id, usuario_atual)
    empresa = db.get(Empresa, pedido.tenant_id)
    if not modo_simulado(empresa=empresa):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmação manual desabilitada: um gateway de pagamento real está configurado.",
        )

    ingresso = confirmar_pedido_ingresso(db, pedido, gateway_ref=f"SIMULADO-{pedido.id}")
    return CompraIngressoResponse(ingresso=_ingresso_para_out(ingresso))


@router.post("/ingressos/{ingresso_id}/cancelar", response_model=IngressoOut)
def cancelar_ingresso(
    ingresso_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    ingresso = db.get(Ingresso, ingresso_id)
    if not ingresso:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingresso não encontrado")

    is_staff = usuario_atual.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN)
    if not is_staff and ingresso.cliente_usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Você não pode cancelar este ingresso")
    if ingresso.status == StatusPassagem.CANCELADA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ingresso já cancelado")

    ingresso.status = StatusPassagem.CANCELADA

    assento = db.get(AssentoSessao, ingresso.assento_sessao_id)
    if assento and assento.ingresso_id == ingresso.id:
        assento.status = StatusPoltrona.LIVRE
        assento.ingresso_id = None

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="cancelamento_ingresso",
        entidade_tipo="ingresso",
        entidade_id=ingresso.id,
        detalhes=f"Código {ingresso.codigo}",
        tenant_id=ingresso.tenant_id,
    )

    db.commit()
    db.refresh(ingresso)
    return _ingresso_para_out(ingresso)


@router.post("/ingressos/{ingresso_id}/reembolsar", response_model=ReembolsoIngressoOut)
def reembolsar_ingresso(
    ingresso_id: int,
    dados: ReembolsarIngressoRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    ingresso = db.get(Ingresso, ingresso_id)
    if not ingresso or ingresso.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingresso não encontrado")
    if ingresso.status != StatusPassagem.CANCELADA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Só é possível reembolsar um ingresso cancelado")
    if ingresso.reembolsado_em:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este ingresso já foi reembolsado")

    valor_reembolso = dados.valor if dados.valor is not None else float(ingresso.preco)
    if valor_reembolso <= 0 or valor_reembolso > float(ingresso.preco):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Valor do reembolso deve ser maior que zero e no máximo R$ {ingresso.preco}",
        )

    ingresso.valor_reembolsado = valor_reembolso
    ingresso.motivo_reembolso = dados.motivo
    ingresso.reembolsado_em = datetime.now(timezone.utc)

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="reembolso_ingresso",
        entidade_tipo="ingresso",
        entidade_id=ingresso.id,
        detalhes=f"Código {ingresso.codigo}, R$ {valor_reembolso:.2f}: {dados.motivo}",
        tenant_id=ingresso.tenant_id,
    )

    db.commit()
    db.refresh(ingresso)

    return ReembolsoIngressoOut(
        ingresso_id=ingresso.id,
        valor_pago=float(ingresso.preco),
        valor_reembolsado=float(ingresso.valor_reembolsado),
        motivo_reembolso=ingresso.motivo_reembolso,
        reembolsado_em=ingresso.reembolsado_em,
    )


@router.get("/sessoes/{sessao_id}/ingressos", response_model=list[IngressoOut])
def listar_ingressos_da_sessao(
    sessao_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    sessao = db.get(Sessao, sessao_id)
    if not sessao or sessao.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessão não encontrada")

    ingressos = (
        db.query(Ingresso)
        .options(joinedload(Ingresso.assento_sessao).joinedload(AssentoSessao.assento_local))
        .filter(Ingresso.sessao_id == sessao_id)
        .order_by(Ingresso.criado_em.desc())
        .all()
    )
    return [_ingresso_para_out(i) for i in ingressos]


@router.get("/ingressos/minhas", response_model=list[IngressoOut])
def meus_ingressos(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    ingressos = (
        db.query(Ingresso)
        .options(
            joinedload(Ingresso.sessao).joinedload(Sessao.local),
            joinedload(Ingresso.assento_sessao).joinedload(AssentoSessao.assento_local),
        )
        .filter(Ingresso.cliente_usuario_id == usuario_atual.id)
        .order_by(Ingresso.criado_em.desc())
        .all()
    )
    return [_ingresso_para_out(i) for i in ingressos]
