from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.core.deps import get_current_user, require_staff
from app.database import get_db
from app.models.enums import StatusPoltrona, TipoOcupacao
from app.models.ocupacao_poltrona import OcupacaoPoltrona
from app.models.parada import Parada
from app.models.poltrona_viagem import PoltronaViagem
from app.models.usuario import Usuario
from app.models.viagem import Viagem
from app.schemas.poltrona import BloquearPoltronaRequest, PoltronaMapaOut
from app.services.auditoria import registrar as registrar_auditoria
from app.services.trecho import (
    buscar_paradas_da_rota,
    calcular_preco_trecho,
    liberar_holds_expirados,
    resolver_trecho,
    status_da_poltrona_no_trecho,
)

router = APIRouter(prefix="/viagens/{viagem_id}/poltronas", tags=["poltronas"])


def _get_viagem_ou_404(db: Session, viagem_id: int) -> Viagem:
    viagem = db.get(Viagem, viagem_id)
    if not viagem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem não encontrada")
    return viagem


def _resolver_trecho(
    db: Session, viagem: Viagem, origem_parada_id: int | None, destino_parada_id: int | None
) -> tuple[Parada, Parada, list[Parada]]:
    """Resolve o trecho pedido. Sem parâmetros, usa a rota inteira
    (origem->destino), mantendo compatibilidade com rotas sem paradas
    intermediárias."""
    paradas = buscar_paradas_da_rota(db, viagem.rota_id)
    if not paradas:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Rota sem paradas cadastradas")

    parada_origem, parada_destino = resolver_trecho(paradas, origem_parada_id, destino_parada_id)
    if not parada_origem or not parada_destino:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parada não encontrada nesta rota")
    if parada_origem.ordem >= parada_destino.ordem:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parada de origem deve vir antes da de destino")

    return parada_origem, parada_destino, paradas


def _para_mapa(
    poltrona: PoltronaViagem,
    ocupacoes: list[OcupacaoPoltrona],
    preco_trecho: float,
    origem_ordem: int,
    destino_ordem: int,
) -> PoltronaMapaOut:
    status_pv, ocupacao = status_da_poltrona_no_trecho(ocupacoes, origem_ordem, destino_ordem)
    return PoltronaMapaOut(
        poltrona_viagem_id=poltrona.id,
        numero=poltrona.poltrona_onibus.numero,
        andar=poltrona.poltrona_onibus.andar,
        fileira=poltrona.poltrona_onibus.fileira,
        coluna=poltrona.poltrona_onibus.coluna,
        categoria=poltrona.poltrona_onibus.categoria,
        preco=round(preco_trecho * float(poltrona.poltrona_onibus.multiplicador_preco), 2),
        status=status_pv,
        hold_expira_em=ocupacao.expira_em if ocupacao and ocupacao.tipo == TipoOcupacao.HOLD else None,
    )


def _ocupacoes_da_poltrona(db: Session, poltrona_viagem_id: int) -> list[OcupacaoPoltrona]:
    return db.query(OcupacaoPoltrona).filter(OcupacaoPoltrona.poltrona_viagem_id == poltrona_viagem_id).all()


@router.get("", response_model=list[PoltronaMapaOut])
def mapa_de_poltronas(
    viagem_id: int,
    origem_parada_id: int | None = None,
    destino_parada_id: int | None = None,
    db: Session = Depends(get_db),
):
    """Mapa público (cliente vê disponibilidade antes de logar). Sem
    origem_parada_id/destino_parada_id, mostra disponibilidade para a
    viagem inteira (origem -> destino da rota)."""
    viagem = _get_viagem_ou_404(db, viagem_id)
    parada_origem, parada_destino, paradas = _resolver_trecho(db, viagem, origem_parada_id, destino_parada_id)

    poltronas = (
        db.query(PoltronaViagem)
        .options(joinedload(PoltronaViagem.poltrona_onibus))
        .filter(PoltronaViagem.viagem_id == viagem_id)
        .all()
    )
    liberar_holds_expirados(db, [p.id for p in poltronas])

    preco_trecho = calcular_preco_trecho(paradas, parada_origem.ordem, parada_destino.ordem, viagem.preco)
    return [
        _para_mapa(p, _ocupacoes_da_poltrona(db, p.id), preco_trecho, parada_origem.ordem, parada_destino.ordem)
        for p in poltronas
    ]


@router.post("/{poltrona_viagem_id}/hold", response_model=PoltronaMapaOut)
def reservar_temporariamente(
    viagem_id: int,
    poltrona_viagem_id: int,
    origem_parada_id: int | None = None,
    destino_parada_id: int | None = None,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    """Bloqueio temporário (hold) enquanto o funcionário ou cliente finaliza a compra, no trecho pedido."""
    viagem = _get_viagem_ou_404(db, viagem_id)
    parada_origem, parada_destino, paradas = _resolver_trecho(db, viagem, origem_parada_id, destino_parada_id)

    poltrona = db.get(PoltronaViagem, poltrona_viagem_id)
    if not poltrona or poltrona.viagem_id != viagem_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poltrona não encontrada")

    liberar_holds_expirados(db, [poltrona.id])
    ocupacoes = _ocupacoes_da_poltrona(db, poltrona.id)
    status_pv, _ = status_da_poltrona_no_trecho(ocupacoes, parada_origem.ordem, parada_destino.ordem)
    if status_pv != StatusPoltrona.LIVRE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Poltrona não está disponível neste trecho")

    nova_ocupacao = OcupacaoPoltrona(
        poltrona_viagem_id=poltrona.id,
        tipo=TipoOcupacao.HOLD,
        parada_origem_ordem=parada_origem.ordem,
        parada_destino_ordem=parada_destino.ordem,
        usuario_id=usuario_atual.id,
        expira_em=datetime.now(timezone.utc) + timedelta(minutes=settings.seat_hold_minutes),
    )
    db.add(nova_ocupacao)
    db.commit()

    preco_trecho = calcular_preco_trecho(paradas, parada_origem.ordem, parada_destino.ordem, viagem.preco)
    return _para_mapa(poltrona, [nova_ocupacao], preco_trecho, parada_origem.ordem, parada_destino.ordem)


@router.post("/{poltrona_viagem_id}/liberar", response_model=PoltronaMapaOut)
def liberar_hold(
    viagem_id: int,
    poltrona_viagem_id: int,
    origem_parada_id: int | None = None,
    destino_parada_id: int | None = None,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    viagem = _get_viagem_ou_404(db, viagem_id)
    parada_origem, parada_destino, paradas = _resolver_trecho(db, viagem, origem_parada_id, destino_parada_id)

    poltrona = db.get(PoltronaViagem, poltrona_viagem_id)
    if not poltrona or poltrona.viagem_id != viagem_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poltrona não encontrada")

    hold = (
        db.query(OcupacaoPoltrona)
        .filter(
            OcupacaoPoltrona.poltrona_viagem_id == poltrona.id,
            OcupacaoPoltrona.tipo == TipoOcupacao.HOLD,
            OcupacaoPoltrona.usuario_id == usuario_atual.id,
            OcupacaoPoltrona.parada_origem_ordem == parada_origem.ordem,
            OcupacaoPoltrona.parada_destino_ordem == parada_destino.ordem,
        )
        .first()
    )
    if hold:
        db.delete(hold)
        db.commit()

    preco_trecho = calcular_preco_trecho(paradas, parada_origem.ordem, parada_destino.ordem, viagem.preco)
    return _para_mapa(poltrona, _ocupacoes_da_poltrona(db, poltrona.id), preco_trecho, parada_origem.ordem, parada_destino.ordem)


@router.post("/{poltrona_viagem_id}/bloquear", response_model=PoltronaMapaOut)
def bloquear_poltrona(
    viagem_id: int,
    poltrona_viagem_id: int,
    dados: BloquearPoltronaRequest,
    origem_parada_id: int | None = None,
    destino_parada_id: int | None = None,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    """Bloqueio administrativo (manutenção, reservada para tripulação, etc.)."""
    viagem = _get_viagem_ou_404(db, viagem_id)
    parada_origem, parada_destino, paradas = _resolver_trecho(db, viagem, origem_parada_id, destino_parada_id)

    poltrona = db.get(PoltronaViagem, poltrona_viagem_id)
    if not poltrona or poltrona.viagem_id != viagem_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poltrona não encontrada")

    liberar_holds_expirados(db, [poltrona.id])
    ocupacoes = _ocupacoes_da_poltrona(db, poltrona.id)
    status_pv, conflito = status_da_poltrona_no_trecho(ocupacoes, parada_origem.ordem, parada_destino.ordem)
    if status_pv == StatusPoltrona.VENDIDA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Poltrona já vendida neste trecho")
    if status_pv == StatusPoltrona.HOLD and conflito and conflito.usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Poltrona em reserva por outro usuário neste trecho")

    nova_ocupacao = OcupacaoPoltrona(
        poltrona_viagem_id=poltrona.id,
        tipo=TipoOcupacao.BLOQUEIO,
        parada_origem_ordem=parada_origem.ordem,
        parada_destino_ordem=parada_destino.ordem,
        usuario_id=usuario_atual.id,
        motivo=dados.motivo,
    )
    db.add(nova_ocupacao)

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="bloqueio_poltrona",
        entidade_tipo="poltrona_viagem",
        entidade_id=poltrona.id,
        detalhes=f"Poltrona {poltrona.poltrona_onibus.numero}, trecho {parada_origem.nome}->{parada_destino.nome}: {dados.motivo}",
        tenant_id=viagem.tenant_id,
    )

    db.commit()
    preco_trecho = calcular_preco_trecho(paradas, parada_origem.ordem, parada_destino.ordem, viagem.preco)
    return _para_mapa(poltrona, [nova_ocupacao], preco_trecho, parada_origem.ordem, parada_destino.ordem)


@router.post("/{poltrona_viagem_id}/desbloquear", response_model=PoltronaMapaOut)
def desbloquear_poltrona(
    viagem_id: int,
    poltrona_viagem_id: int,
    origem_parada_id: int | None = None,
    destino_parada_id: int | None = None,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    viagem = _get_viagem_ou_404(db, viagem_id)
    parada_origem, parada_destino, paradas = _resolver_trecho(db, viagem, origem_parada_id, destino_parada_id)

    poltrona = db.get(PoltronaViagem, poltrona_viagem_id)
    if not poltrona or poltrona.viagem_id != viagem_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poltrona não encontrada")

    bloqueio = (
        db.query(OcupacaoPoltrona)
        .filter(
            OcupacaoPoltrona.poltrona_viagem_id == poltrona.id,
            OcupacaoPoltrona.tipo == TipoOcupacao.BLOQUEIO,
            OcupacaoPoltrona.parada_origem_ordem == parada_origem.ordem,
            OcupacaoPoltrona.parada_destino_ordem == parada_destino.ordem,
        )
        .first()
    )
    if not bloqueio:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Poltrona não está bloqueada nesse trecho")

    db.delete(bloqueio)

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="desbloqueio_poltrona",
        entidade_tipo="poltrona_viagem",
        entidade_id=poltrona.id,
        detalhes=f"Poltrona {poltrona.poltrona_onibus.numero}, trecho {parada_origem.nome}->{parada_destino.nome}",
        tenant_id=viagem.tenant_id,
    )

    db.commit()
    preco_trecho = calcular_preco_trecho(paradas, parada_origem.ordem, parada_destino.ordem, viagem.preco)
    return _para_mapa(poltrona, _ocupacoes_da_poltrona(db, poltrona.id), preco_trecho, parada_origem.ordem, parada_destino.ordem)
