from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_staff
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import StatusPedidoPagamento, TipoOcupacao, UserRole
from app.models.ocupacao_poltrona import OcupacaoPoltrona
from app.models.parada import Parada
from app.models.pedido_pagamento import PedidoPagamento
from app.models.poltrona_viagem import PoltronaViagem
from app.models.usuario import Usuario
from app.models.viagem import Viagem
from app.schemas.passagem import PassagemOut
from app.schemas.pedido_pagamento import PedidoPagamentoOut
from app.services.pagamento_provider import modo_simulado
from app.routers.passagens import _criar_passagem_confirmada, _gerar_localizador_unico

router = APIRouter(prefix="/pedidos-pagamento", tags=["pedidos-pagamento"])


def _expirar_se_vencido(db: Session, pedido: PedidoPagamento) -> None:
    if pedido.status == StatusPedidoPagamento.PENDENTE and pedido.expira_em < datetime.utcnow():
        pedido.status = StatusPedidoPagamento.EXPIRADO
        db.commit()
        db.refresh(pedido)


def _para_out(pedido: PedidoPagamento, paradas_por_id: dict[int, Parada], *, pagamento_simulado: bool) -> PedidoPagamentoOut:
    parada_origem = paradas_por_id.get(pedido.parada_origem_id)
    parada_destino = paradas_por_id.get(pedido.parada_destino_id)
    return PedidoPagamentoOut(
        id=pedido.id,
        status=pedido.status,
        valor=float(pedido.valor),
        forma_pagamento=pedido.forma_pagamento,
        pix_copia_cola=pedido.pix_copia_cola,
        expira_em=pedido.expira_em,
        criado_em=pedido.criado_em,
        passagem_id=pedido.passagem_id,
        viagem_id=pedido.viagem_id,
        cliente_nome=pedido.cliente_nome,
        cliente_documento=pedido.cliente_documento,
        poltrona_numero=pedido.poltrona_viagem.poltrona_onibus.numero if pedido.poltrona_viagem else None,
        origem_trecho=parada_origem.nome if parada_origem else None,
        destino_trecho=parada_destino.nome if parada_destino else None,
        pagamento_simulado=pagamento_simulado,
    )


@router.get("/viagem/{viagem_id}", response_model=list[PedidoPagamentoOut])
def listar_pedidos_pendentes_da_viagem(
    viagem_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    """Pedidos de pagamento (Pix ou cobrança manual) ainda pendentes de
    confirmação pra essa viagem — passageiros que começaram a compra mas o
    pagamento ainda não foi confirmado nem expirou. Não aparecem na lista
    normal de passageiros (que só mostra Passagem, criada só depois da
    confirmação)."""
    viagem = db.get(Viagem, viagem_id)
    if not viagem or viagem.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem não encontrada")

    pedidos = (
        db.query(PedidoPagamento)
        .options(joinedload(PedidoPagamento.poltrona_viagem).joinedload(PoltronaViagem.poltrona_onibus))
        .filter(PedidoPagamento.viagem_id == viagem_id, PedidoPagamento.status == StatusPedidoPagamento.PENDENTE)
        .all()
    )
    for pedido in pedidos:
        _expirar_se_vencido(db, pedido)
    ainda_pendentes = [p for p in pedidos if p.status == StatusPedidoPagamento.PENDENTE]

    ids_paradas = {p.parada_origem_id for p in ainda_pendentes} | {p.parada_destino_id for p in ainda_pendentes}
    paradas_por_id = {p.id: p for p in db.query(Parada).filter(Parada.id.in_(ids_paradas)).all()} if ids_paradas else {}

    simulado = modo_simulado(empresa=db.get(Empresa, viagem.tenant_id))
    return [_para_out(p, paradas_por_id, pagamento_simulado=simulado) for p in ainda_pendentes]


def _buscar_pedido_do_usuario(db: Session, pedido_id: int, usuario_atual: Usuario) -> PedidoPagamento:
    pedido = db.get(PedidoPagamento, pedido_id)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido de pagamento não encontrado")
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


@router.get("/{pedido_id}", response_model=PedidoPagamentoOut)
def consultar_pedido(
    pedido_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    pedido = _buscar_pedido_do_usuario(db, pedido_id, usuario_atual)
    saida = PedidoPagamentoOut.model_validate(pedido)
    saida.pagamento_simulado = modo_simulado(empresa=db.get(Empresa, pedido.tenant_id))
    return saida


def confirmar_pedido_pagamento(db: Session, pedido: PedidoPagamento, gateway_ref: str):
    """Cria a passagem de verdade e fecha o pedido — chamado tanto pelo
    endpoint de confirmação manual/simulada (staff clica "já paguei")
    quanto pelo webhook do Mercado Pago (`app/routers/webhooks.py`) quando
    um Pix real cai de verdade. `gateway_ref` fica registrado no
    `Pagamento` gerado, então dá pra saber depois se uma venda foi
    simulada (`SIMULADO-...`) ou veio de um webhook real (id do MP)."""
    if pedido.status == StatusPedidoPagamento.CONFIRMADO:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pedido já confirmado")
    if pedido.status != StatusPedidoPagamento.PENDENTE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pedido não está mais pendente (expirado ou cancelado)")

    viagem = db.get(Viagem, pedido.viagem_id)
    poltrona = db.get(PoltronaViagem, pedido.poltrona_viagem_id)
    parada_origem = db.get(Parada, pedido.parada_origem_id)
    parada_destino = db.get(Parada, pedido.parada_destino_id)
    if not viagem or not poltrona or not parada_origem or not parada_destino:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem, poltrona ou trecho não encontrado")

    hold = (
        db.query(OcupacaoPoltrona)
        .filter(
            OcupacaoPoltrona.poltrona_viagem_id == poltrona.id,
            OcupacaoPoltrona.tipo == TipoOcupacao.HOLD,
            OcupacaoPoltrona.parada_origem_ordem == parada_origem.ordem,
            OcupacaoPoltrona.parada_destino_ordem == parada_destino.ordem,
        )
        .first()
    )

    usuario_do_pedido = db.get(Usuario, pedido.usuario_id)

    passagem = _criar_passagem_confirmada(
        db,
        viagem=viagem,
        poltrona=poltrona,
        parada_origem=parada_origem,
        parada_destino=parada_destino,
        localizador=_gerar_localizador_unico(db),
        cliente_nome=pedido.cliente_nome,
        cliente_documento=pedido.cliente_documento,
        cliente_telefone=pedido.cliente_telefone,
        tipo_documento=pedido.tipo_documento,
        categoria_passageiro=pedido.categoria_passageiro,
        cliente_usuario_id=usuario_do_pedido.id if usuario_do_pedido and usuario_do_pedido.role == UserRole.CLIENTE else None,
        vendido_por_usuario_id=usuario_do_pedido.id
        if usuario_do_pedido and usuario_do_pedido.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN)
        else None,
        parceiro_id=pedido.parceiro_id,
        preco_final=float(pedido.valor),
        forma_pagamento=pedido.forma_pagamento,
        gateway_ref=gateway_ref,
        hold_para_remover=hold,
        usuario_para_notificar=usuario_do_pedido,
        codigo_cupom=pedido.codigo_cupom,
    )

    pedido.status = StatusPedidoPagamento.CONFIRMADO
    pedido.passagem_id = passagem.id
    db.commit()

    return passagem


@router.post("/{pedido_id}/confirmar-simulado", response_model=PassagemOut)
def confirmar_pagamento_simulado(
    pedido_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    """Simula o webhook que um gateway real chamaria quando o Pix cai na
    conta. Só existe em modo simulado (sem GOTUR_GATEWAY_API_KEY) — com um
    gateway real configurado, é o próprio webhook do Mercado Pago que
    confirma (ver app/routers/webhooks.py), não o usuário clicando num
    botão."""
    pedido = _buscar_pedido_do_usuario(db, pedido_id, usuario_atual)

    empresa_do_pedido = db.get(Empresa, pedido.tenant_id)
    if not modo_simulado(empresa_do_pedido):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmação manual desabilitada: um gateway de pagamento real está configurado.",
        )

    return confirmar_pedido_pagamento(db, pedido, gateway_ref=f"SIMULADO-{pedido.id}")


@router.post("/{pedido_id}/cancelar", status_code=status.HTTP_204_NO_CONTENT)
def cancelar_pedido_pendente(
    pedido_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    """Desiste de um pedido pendente antes de expirar sozinho — libera a
    poltrona na hora em vez de esperar o prazo do Pix/confirmação manual
    passar. Só a equipe da empresa pode (o cliente que desistiu é só não
    pagar e deixar expirar)."""
    pedido = db.get(PedidoPagamento, pedido_id)
    if not pedido or pedido.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido de pagamento não encontrado")
    if pedido.status != StatusPedidoPagamento.PENDENTE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pedido não está mais pendente")

    parada_origem = db.get(Parada, pedido.parada_origem_id)
    parada_destino = db.get(Parada, pedido.parada_destino_id)
    hold = (
        db.query(OcupacaoPoltrona)
        .filter(
            OcupacaoPoltrona.poltrona_viagem_id == pedido.poltrona_viagem_id,
            OcupacaoPoltrona.tipo == TipoOcupacao.HOLD,
            OcupacaoPoltrona.parada_origem_ordem == parada_origem.ordem,
            OcupacaoPoltrona.parada_destino_ordem == parada_destino.ordem,
        )
        .first()
    )
    if hold:
        db.delete(hold)

    pedido.status = StatusPedidoPagamento.CANCELADO
    db.commit()
