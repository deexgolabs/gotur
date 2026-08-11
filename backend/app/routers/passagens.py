from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_staff
from app.database import get_db
from app.models.avaliacao import Avaliacao
from app.models.enums import FormaPagamento, StatusPassagem, StatusPoltrona, TipoOcupacao, UserRole
from app.models.ocupacao_poltrona import OcupacaoPoltrona
from app.models.pagamento import Pagamento
from app.models.parada import Parada
from app.models.passagem import Passagem
from app.models.pedido_pagamento import PedidoPagamento
from app.models.poltrona_viagem import PoltronaViagem
from app.models.usuario import Usuario
from app.models.viagem import Viagem
from app.schemas.avaliacao import AvaliacaoOut, AvaliarRequest
from app.schemas.passagem import NfseOut, PassagemDetalheOut, PassagemOut, VenderPassagemRequest
from app.schemas.pedido_pagamento import CompraPassagemResponse, PedidoPagamentoOut
from app.schemas.reembolso import ReembolsarRequest, ReembolsoOut
from app.services.auditoria import registrar as registrar_auditoria
from app.services.codigo import gerar_localizador
from app.services.cupom import CupomInvalido, aplicar_cupom
from app.services.nfse_provider import obter_nfse_provider
from app.services.notificacoes import enviar_confirmacao_compra
from app.services.pagamento_provider import obter_provider
from app.services.trecho import (
    buscar_paradas_da_rota,
    calcular_preco_trecho,
    liberar_holds_expirados,
    resolver_trecho,
    status_da_poltrona_no_trecho,
)
from app.services.whatsapp_service import enviar_confirmacao_compra_whatsapp

router = APIRouter(prefix="/viagens/{viagem_id}/passagens", tags=["passagens"])
meu_router = APIRouter(prefix="/passagens", tags=["passagens"])


def _gerar_localizador_unico(db: Session) -> str:
    localizador = gerar_localizador()
    while db.query(Passagem).filter(Passagem.localizador == localizador).first():
        localizador = gerar_localizador()
    return localizador


def _criar_passagem_confirmada(
    db: Session,
    *,
    viagem: Viagem,
    poltrona: PoltronaViagem,
    parada_origem: Parada,
    parada_destino: Parada,
    localizador: str,
    cliente_nome: str,
    cliente_documento: str,
    cliente_usuario_id: int | None,
    vendido_por_usuario_id: int | None,
    preco_final: float,
    forma_pagamento: FormaPagamento,
    gateway_ref: str | None,
    hold_para_remover: OcupacaoPoltrona | None,
    usuario_para_notificar: Usuario | None,
    codigo_cupom: str | None = None,
) -> Passagem:
    passagem = Passagem(
        tenant_id=viagem.tenant_id,
        viagem_id=viagem.id,
        poltrona_viagem_id=poltrona.id,
        parada_origem_id=parada_origem.id,
        parada_destino_id=parada_destino.id,
        cliente_usuario_id=cliente_usuario_id,
        cliente_nome=cliente_nome,
        cliente_documento=cliente_documento,
        vendido_por_usuario_id=vendido_por_usuario_id,
        preco=preco_final,
        codigo_cupom=codigo_cupom,
        status=StatusPassagem.CONFIRMADA,
        localizador=localizador,
    )
    db.add(passagem)
    db.flush()

    db.add(
        Pagamento(
            passagem_id=passagem.id,
            forma_pagamento=forma_pagamento,
            valor=preco_final,
            gateway_ref=gateway_ref,
        )
    )

    if hold_para_remover is not None:
        db.delete(hold_para_remover)
    db.add(
        OcupacaoPoltrona(
            poltrona_viagem_id=poltrona.id,
            tipo=TipoOcupacao.VENDA,
            parada_origem_ordem=parada_origem.ordem,
            parada_destino_ordem=parada_destino.ordem,
            passagem_id=passagem.id,
        )
    )

    registrar_auditoria(
        db,
        usuario=usuario_para_notificar,
        acao="venda_passagem",
        entidade_tipo="passagem",
        entidade_id=passagem.id,
        detalhes=f"Localizador {localizador}, poltrona {poltrona.poltrona_onibus.numero}, trecho {parada_origem.nome}->{parada_destino.nome}, R$ {preco_final}",
        tenant_id=viagem.tenant_id,
    )

    db.commit()
    db.refresh(passagem)

    if usuario_para_notificar and usuario_para_notificar.role == UserRole.CLIENTE:
        enviar_confirmacao_compra(
            destinatario_email=usuario_para_notificar.email,
            cliente_nome=passagem.cliente_nome,
            localizador=passagem.localizador,
            origem=parada_origem.nome,
            destino=parada_destino.nome,
            data_hora_partida=viagem.data_hora_partida,
            numero_poltrona=poltrona.poltrona_onibus.numero,
            preco=float(passagem.preco),
        )
        enviar_confirmacao_compra_whatsapp(
            telefone=usuario_para_notificar.telefone,
            cliente_nome=passagem.cliente_nome,
            localizador=passagem.localizador,
            origem=parada_origem.nome,
            destino=parada_destino.nome,
            data_hora_partida=viagem.data_hora_partida,
            numero_poltrona=poltrona.poltrona_onibus.numero,
        )

    return passagem


@router.post("", response_model=CompraPassagemResponse, status_code=status.HTTP_201_CREATED)
def vender_passagem(
    viagem_id: int,
    dados: VenderPassagemRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    viagem = db.get(Viagem, viagem_id)
    if not viagem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem não encontrada")

    paradas = buscar_paradas_da_rota(db, viagem.rota_id)
    parada_origem, parada_destino = resolver_trecho(paradas, dados.parada_origem_id, dados.parada_destino_id)
    if not parada_origem or not parada_destino:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parada não encontrada nesta rota")
    if parada_origem.ordem >= parada_destino.ordem:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parada de origem deve vir antes da de destino")

    poltrona = db.get(PoltronaViagem, dados.poltrona_viagem_id)
    if not poltrona or poltrona.viagem_id != viagem_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poltrona não encontrada")

    is_staff = usuario_atual.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN)

    liberar_holds_expirados(db, [poltrona.id])
    ocupacoes = db.query(OcupacaoPoltrona).filter(OcupacaoPoltrona.poltrona_viagem_id == poltrona.id).all()
    status_pv, conflito = status_da_poltrona_no_trecho(ocupacoes, parada_origem.ordem, parada_destino.ordem)

    pode_confirmar = status_pv == StatusPoltrona.LIVRE or (
        status_pv == StatusPoltrona.HOLD and conflito and (is_staff or conflito.usuario_id == usuario_atual.id)
    )
    if not pode_confirmar:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Poltrona não está disponível para venda neste trecho")

    preco_final = round(
        calcular_preco_trecho(paradas, parada_origem.ordem, parada_destino.ordem, viagem.preco)
        * float(poltrona.poltrona_onibus.multiplicador_preco),
        2,
    )

    codigo_cupom_aplicado = None
    if dados.codigo_cupom:
        try:
            cupom, desconto = aplicar_cupom(db, tenant_id=viagem.tenant_id, codigo=dados.codigo_cupom, preco_base=preco_final)
        except CupomInvalido as erro:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(erro))
        preco_final = round(preco_final - desconto, 2)
        codigo_cupom_aplicado = cupom.codigo

    hold_existente = conflito if (conflito and conflito.tipo == TipoOcupacao.HOLD) else None

    resultado_cobranca = obter_provider().cobrar(
        forma_pagamento=dados.forma_pagamento,
        valor=preco_final,
        referencia_pedido=f"viagem-{viagem_id}-poltrona-{poltrona.id}",
    )

    if resultado_cobranca.status == "pendente":
        # Pix ainda não caiu: segura o assento até a confirmação (simulada
        # no v1, webhook do gateway real no futuro) em vez de vender agora.
        if hold_existente is not None:
            hold_existente.expira_em = resultado_cobranca.pix_expira_em
            if hold_existente.usuario_id is None:
                hold_existente.usuario_id = usuario_atual.id
        else:
            db.add(
                OcupacaoPoltrona(
                    poltrona_viagem_id=poltrona.id,
                    tipo=TipoOcupacao.HOLD,
                    parada_origem_ordem=parada_origem.ordem,
                    parada_destino_ordem=parada_destino.ordem,
                    usuario_id=usuario_atual.id,
                    expira_em=resultado_cobranca.pix_expira_em,
                )
            )

        pedido = PedidoPagamento(
            tenant_id=viagem.tenant_id,
            viagem_id=viagem_id,
            poltrona_viagem_id=poltrona.id,
            parada_origem_id=parada_origem.id,
            parada_destino_id=parada_destino.id,
            usuario_id=usuario_atual.id,
            cliente_nome=dados.cliente_nome,
            cliente_documento=dados.cliente_documento,
            forma_pagamento=dados.forma_pagamento,
            valor=preco_final,
            codigo_cupom=codigo_cupom_aplicado,
            pix_copia_cola=resultado_cobranca.pix_copia_cola,
            expira_em=resultado_cobranca.pix_expira_em,
        )
        db.add(pedido)
        db.commit()
        db.refresh(pedido)
        return CompraPassagemResponse(pedido_pagamento=PedidoPagamentoOut.model_validate(pedido))

    passagem = _criar_passagem_confirmada(
        db,
        viagem=viagem,
        poltrona=poltrona,
        parada_origem=parada_origem,
        parada_destino=parada_destino,
        localizador=_gerar_localizador_unico(db),
        cliente_nome=dados.cliente_nome,
        cliente_documento=dados.cliente_documento,
        cliente_usuario_id=usuario_atual.id if usuario_atual.role == UserRole.CLIENTE else None,
        vendido_por_usuario_id=usuario_atual.id if is_staff else None,
        preco_final=preco_final,
        forma_pagamento=dados.forma_pagamento,
        gateway_ref=resultado_cobranca.gateway_ref,
        hold_para_remover=hold_existente,
        usuario_para_notificar=usuario_atual,
        codigo_cupom=codigo_cupom_aplicado,
    )
    return CompraPassagemResponse(passagem=passagem)


@router.post("/{passagem_id}/cancelar", response_model=PassagemOut)
def cancelar_passagem(
    viagem_id: int,
    passagem_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    passagem = db.get(Passagem, passagem_id)
    if not passagem or passagem.viagem_id != viagem_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passagem não encontrada")

    is_staff = usuario_atual.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN)
    if not is_staff and passagem.cliente_usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Você não pode cancelar esta passagem")
    if passagem.status == StatusPassagem.CANCELADA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Passagem já cancelada")

    passagem.status = StatusPassagem.CANCELADA

    ocupacao_venda = (
        db.query(OcupacaoPoltrona)
        .filter(OcupacaoPoltrona.passagem_id == passagem.id, OcupacaoPoltrona.tipo == TipoOcupacao.VENDA)
        .first()
    )
    if ocupacao_venda:
        db.delete(ocupacao_venda)

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="cancelamento_passagem",
        entidade_tipo="passagem",
        entidade_id=passagem.id,
        detalhes=f"Localizador {passagem.localizador}",
        tenant_id=passagem.tenant_id,
    )

    db.commit()
    db.refresh(passagem)
    return passagem


@router.post("/{passagem_id}/reembolsar", response_model=ReembolsoOut)
def reembolsar_passagem(
    viagem_id: int,
    passagem_id: int,
    dados: ReembolsarRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    """Registra o reembolso de uma passagem já cancelada. Separado do
    cancelamento para permitir cancelar sem reembolsar imediatamente (ex:
    aguardando aprovação financeira) e para manter o valor/motivo do
    reembolso rastreados junto ao pagamento original."""
    passagem = db.get(Passagem, passagem_id)
    if not passagem or passagem.viagem_id != viagem_id or passagem.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passagem não encontrada")
    if passagem.status != StatusPassagem.CANCELADA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Só é possível reembolsar uma passagem cancelada")

    pagamento = passagem.pagamento
    if not pagamento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pagamento não encontrado para esta passagem")
    if pagamento.reembolsado_em:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta passagem já foi reembolsada")

    valor_reembolso = dados.valor if dados.valor is not None else float(pagamento.valor)
    if valor_reembolso <= 0 or valor_reembolso > float(pagamento.valor):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Valor do reembolso deve ser maior que zero e no máximo R$ {pagamento.valor}",
        )

    pagamento.valor_reembolsado = valor_reembolso
    pagamento.motivo_reembolso = dados.motivo
    pagamento.reembolsado_em = datetime.now(timezone.utc)

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="reembolso",
        entidade_tipo="passagem",
        entidade_id=passagem.id,
        detalhes=f"Localizador {passagem.localizador}, R$ {valor_reembolso:.2f}: {dados.motivo}",
        tenant_id=passagem.tenant_id,
    )

    db.commit()
    db.refresh(pagamento)

    return ReembolsoOut(
        passagem_id=passagem.id,
        valor_pago=float(pagamento.valor),
        valor_reembolsado=float(pagamento.valor_reembolsado),
        motivo_reembolso=pagamento.motivo_reembolso,
        reembolsado_em=pagamento.reembolsado_em,
    )


@router.post("/{passagem_id}/nfse", response_model=NfseOut)
def emitir_nfse(
    viagem_id: int,
    passagem_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    """Terreno pronto: sem um agregador de NFS-e configurado (ver
    app/services/nfse_provider.py), só registra no log e devolve
    status "simulada" — não emite nada de verdade."""
    passagem = db.get(Passagem, passagem_id)
    if not passagem or passagem.viagem_id != viagem_id or passagem.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passagem não encontrada")

    resultado = obter_nfse_provider().emitir(
        referencia=passagem.localizador,
        valor=float(passagem.preco),
        cliente_nome=passagem.cliente_nome,
        cliente_documento=passagem.cliente_documento,
        descricao=f"Passagem rodoviária — localizador {passagem.localizador}",
    )

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="emissao_nfse",
        entidade_tipo="passagem",
        entidade_id=passagem.id,
        detalhes=f"Localizador {passagem.localizador}: {resultado.status}",
        tenant_id=passagem.tenant_id,
    )

    return NfseOut(numero=resultado.numero, status=resultado.status, url_pdf=resultado.url_pdf, chave_acesso=resultado.chave_acesso)


@router.get("", response_model=list[PassagemOut])
def listar_passagens_da_viagem(
    viagem_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    if usuario_atual.role not in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito à equipe da empresa")
    return (
        db.query(Passagem)
        .options(joinedload(Passagem.parada_origem), joinedload(Passagem.parada_destino), joinedload(Passagem.pagamento))
        .filter(Passagem.viagem_id == viagem_id)
        .order_by(Passagem.criado_em.desc())
        .all()
    )


@meu_router.get("/minhas", response_model=list[PassagemDetalheOut])
def minhas_passagens(
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    """`tenant_id` é opcional: usado pela loja white-label (/loja/{slug})
    pra mostrar só as passagens compradas naquela empresa; sem ele, mostra
    todas (portal genérico do cliente)."""
    query = (
        db.query(Passagem)
        .options(
            joinedload(Passagem.viagem).joinedload(Viagem.onibus),
            joinedload(Passagem.poltrona_viagem).joinedload(PoltronaViagem.poltrona_onibus),
            joinedload(Passagem.parada_origem),
            joinedload(Passagem.parada_destino),
            joinedload(Passagem.pagamento),
        )
        .filter(Passagem.cliente_usuario_id == usuario_atual.id)
    )
    if tenant_id is not None:
        query = query.filter(Passagem.tenant_id == tenant_id)
    passagens = query.order_by(Passagem.criado_em.desc()).all()

    avaliacoes_por_passagem = {
        a.passagem_id: a
        for a in db.query(Avaliacao).filter(Avaliacao.passagem_id.in_([p.id for p in passagens])).all()
    }
    agora = datetime.now(timezone.utc)

    resultado = []
    for p in passagens:
        avaliacao = avaliacoes_por_passagem.get(p.id)
        data_partida = p.viagem.data_hora_partida
        if data_partida.tzinfo is None:
            data_partida = data_partida.replace(tzinfo=timezone.utc)
        pode_avaliar = p.status == StatusPassagem.CONFIRMADA and data_partida < agora and avaliacao is None

        resultado.append(
            PassagemDetalheOut(
                id=p.id,
                viagem_id=p.viagem_id,
                poltrona_viagem_id=p.poltrona_viagem_id,
                cliente_nome=p.cliente_nome,
                cliente_documento=p.cliente_documento,
                preco=float(p.preco),
                status=p.status,
                localizador=p.localizador,
                criado_em=p.criado_em,
                reembolsado_em=p.reembolsado_em,
                valor_reembolsado=p.valor_reembolsado,
                origem_trecho=p.origem_trecho,
                destino_trecho=p.destino_trecho,
                origem=p.origem_trecho,
                destino=p.destino_trecho,
                data_hora_partida=p.viagem.data_hora_partida,
                numero_poltrona=p.poltrona_viagem.poltrona_onibus.numero,
                empresa_nome=p.viagem.onibus.empresa.nome if p.viagem.onibus.empresa else "",
                pode_avaliar=pode_avaliar,
                nota_avaliacao=avaliacao.nota if avaliacao else None,
            )
        )
    return resultado


@meu_router.post("/{passagem_id}/avaliar", response_model=AvaliacaoOut, status_code=status.HTTP_201_CREATED)
def avaliar_passagem(
    passagem_id: int,
    dados: AvaliarRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    passagem = db.get(Passagem, passagem_id)
    if not passagem or passagem.cliente_usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passagem não encontrada")
    if passagem.status != StatusPassagem.CONFIRMADA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Só é possível avaliar uma passagem confirmada")

    viagem = db.get(Viagem, passagem.viagem_id)
    data_partida = viagem.data_hora_partida
    if data_partida.tzinfo is None:
        data_partida = data_partida.replace(tzinfo=timezone.utc)
    if data_partida >= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A viagem ainda não aconteceu")

    if db.query(Avaliacao).filter(Avaliacao.passagem_id == passagem_id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta passagem já foi avaliada")

    avaliacao = Avaliacao(
        tenant_id=passagem.tenant_id,
        passagem_id=passagem_id,
        nota=dados.nota,
        comentario=dados.comentario,
    )
    db.add(avaliacao)
    db.commit()
    db.refresh(avaliacao)
    return AvaliacaoOut(
        id=avaliacao.id,
        passagem_id=avaliacao.passagem_id,
        nota=avaliacao.nota,
        comentario=avaliacao.comentario,
        criado_em=avaliacao.criado_em,
        cliente_nome=passagem.cliente_nome,
        origem=passagem.origem_trecho,
        destino=passagem.destino_trecho,
    )
