from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
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
    return PedidoPagamentoOut.model_validate(pedido)


@router.post("/{pedido_id}/confirmar-simulado", response_model=PassagemOut)
def confirmar_pagamento_simulado(
    pedido_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    """Simula o webhook que um gateway real chamaria quando o Pix cai na
    conta. Só existe em modo simulado (sem GOTUR_GATEWAY_API_KEY) — com um
    gateway real configurado, é o próprio gateway que confirma o pagamento,
    não o usuário clicando num botão."""
    if not modo_simulado():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmação manual desabilitada: um gateway de pagamento real está configurado.",
        )

    pedido = _buscar_pedido_do_usuario(db, pedido_id, usuario_atual)
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
        gateway_ref=f"SIMULADO-{pedido.id}",
        hold_para_remover=hold,
        usuario_para_notificar=usuario_do_pedido,
        codigo_cupom=pedido.codigo_cupom,
    )

    pedido.status = StatusPedidoPagamento.CONFIRMADO
    pedido.passagem_id = passagem.id
    db.commit()

    return passagem
