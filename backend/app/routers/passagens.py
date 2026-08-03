from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user
from app.database import get_db
from app.models.enums import StatusPassagem, StatusPoltrona, UserRole
from app.models.pagamento import Pagamento
from app.models.passagem import Passagem
from app.models.poltrona_viagem import PoltronaViagem
from app.models.usuario import Usuario
from app.models.viagem import Viagem
from app.schemas.passagem import PassagemDetalheOut, PassagemOut, VenderPassagemRequest
from app.services.codigo import gerar_localizador
from app.services.notificacoes import enviar_confirmacao_compra
from app.services.pagamento_provider import obter_provider

router = APIRouter(prefix="/viagens/{viagem_id}/passagens", tags=["passagens"])
meu_router = APIRouter(prefix="/passagens", tags=["passagens"])


@router.post("", response_model=PassagemOut, status_code=status.HTTP_201_CREATED)
def vender_passagem(
    viagem_id: int,
    dados: VenderPassagemRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    viagem = db.get(Viagem, viagem_id)
    if not viagem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem não encontrada")

    poltrona = db.get(PoltronaViagem, dados.poltrona_viagem_id)
    if not poltrona or poltrona.viagem_id != viagem_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poltrona não encontrada")

    is_staff = usuario_atual.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN)
    pode_confirmar = poltrona.status == StatusPoltrona.LIVRE or (
        poltrona.status == StatusPoltrona.HOLD and (is_staff or poltrona.hold_usuario_id == usuario_atual.id)
    )
    if not pode_confirmar:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Poltrona não está disponível para venda")

    localizador = gerar_localizador()
    while db.query(Passagem).filter(Passagem.localizador == localizador).first():
        localizador = gerar_localizador()

    passagem = Passagem(
        tenant_id=viagem.tenant_id,
        viagem_id=viagem_id,
        poltrona_viagem_id=poltrona.id,
        cliente_usuario_id=usuario_atual.id if usuario_atual.role == UserRole.CLIENTE else None,
        cliente_nome=dados.cliente_nome,
        cliente_documento=dados.cliente_documento,
        vendido_por_usuario_id=usuario_atual.id if is_staff else None,
        preco=viagem.preco,
        status=StatusPassagem.CONFIRMADA,
        localizador=localizador,
    )
    db.add(passagem)
    db.flush()

    resultado_cobranca = obter_provider().cobrar(
        forma_pagamento=dados.forma_pagamento,
        valor=float(viagem.preco),
        referencia_pedido=localizador,
    )
    db.add(
        Pagamento(
            passagem_id=passagem.id,
            forma_pagamento=dados.forma_pagamento,
            valor=viagem.preco,
            gateway_ref=resultado_cobranca.gateway_ref,
        )
    )

    poltrona.status = StatusPoltrona.VENDIDA
    poltrona.hold_expira_em = None
    poltrona.hold_usuario_id = None

    db.commit()
    db.refresh(passagem)

    if usuario_atual.role == UserRole.CLIENTE:
        enviar_confirmacao_compra(
            destinatario_email=usuario_atual.email,
            cliente_nome=passagem.cliente_nome,
            localizador=passagem.localizador,
            origem=viagem.rota.origem,
            destino=viagem.rota.destino,
            data_hora_partida=viagem.data_hora_partida,
            numero_poltrona=poltrona.poltrona_onibus.numero,
            preco=float(passagem.preco),
        )

    return passagem


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
    poltrona = db.get(PoltronaViagem, passagem.poltrona_viagem_id)
    if poltrona:
        poltrona.status = StatusPoltrona.LIVRE

    db.commit()
    db.refresh(passagem)
    return passagem


@router.get("", response_model=list[PassagemOut])
def listar_passagens_da_viagem(
    viagem_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    if usuario_atual.role not in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito à equipe da empresa")
    return db.query(Passagem).filter(Passagem.viagem_id == viagem_id).order_by(Passagem.criado_em.desc()).all()


@meu_router.get("/minhas", response_model=list[PassagemDetalheOut])
def minhas_passagens(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    passagens = (
        db.query(Passagem)
        .options(
            joinedload(Passagem.viagem).joinedload(Viagem.rota),
            joinedload(Passagem.viagem).joinedload(Viagem.onibus),
            joinedload(Passagem.poltrona_viagem).joinedload(PoltronaViagem.poltrona_onibus),
        )
        .filter(Passagem.cliente_usuario_id == usuario_atual.id)
        .order_by(Passagem.criado_em.desc())
        .all()
    )

    resultado = []
    for p in passagens:
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
                origem=p.viagem.rota.origem,
                destino=p.viagem.rota.destino,
                data_hora_partida=p.viagem.data_hora_partida,
                numero_poltrona=p.poltrona_viagem.poltrona_onibus.numero,
                empresa_nome=p.viagem.onibus.empresa.nome if p.viagem.onibus.empresa else "",
            )
        )
    return resultado
