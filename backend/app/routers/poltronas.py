from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.core.deps import get_current_user, require_staff
from app.database import get_db
from app.models.enums import StatusPoltrona
from app.models.poltrona_viagem import PoltronaViagem
from app.models.usuario import Usuario
from app.models.viagem import Viagem
from app.schemas.poltrona import BloquearPoltronaRequest, PoltronaMapaOut

router = APIRouter(prefix="/viagens/{viagem_id}/poltronas", tags=["poltronas"])


def _liberar_holds_expirados(db: Session, viagem_id: int) -> None:
    agora = datetime.now(timezone.utc)
    expirados = (
        db.query(PoltronaViagem)
        .filter(
            PoltronaViagem.viagem_id == viagem_id,
            PoltronaViagem.status == StatusPoltrona.HOLD,
            PoltronaViagem.hold_expira_em < agora,
        )
        .all()
    )
    for p in expirados:
        p.status = StatusPoltrona.LIVRE
        p.hold_expira_em = None
        p.hold_usuario_id = None
    if expirados:
        db.commit()


def _get_viagem_ou_404(db: Session, viagem_id: int) -> Viagem:
    viagem = db.get(Viagem, viagem_id)
    if not viagem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem não encontrada")
    return viagem


@router.get("", response_model=list[PoltronaMapaOut])
def mapa_de_poltronas(viagem_id: int, db: Session = Depends(get_db)):
    """Mapa público (cliente vê disponibilidade antes de logar)."""
    _get_viagem_ou_404(db, viagem_id)
    _liberar_holds_expirados(db, viagem_id)

    poltronas = (
        db.query(PoltronaViagem)
        .options(joinedload(PoltronaViagem.poltrona_onibus))
        .filter(PoltronaViagem.viagem_id == viagem_id)
        .all()
    )
    return [
        PoltronaMapaOut(
            poltrona_viagem_id=p.id,
            numero=p.poltrona_onibus.numero,
            andar=p.poltrona_onibus.andar,
            fileira=p.poltrona_onibus.fileira,
            coluna=p.poltrona_onibus.coluna,
            status=p.status,
            hold_expira_em=p.hold_expira_em,
        )
        for p in poltronas
    ]


@router.post("/{poltrona_viagem_id}/hold", response_model=PoltronaMapaOut)
def reservar_temporariamente(
    viagem_id: int,
    poltrona_viagem_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    """Bloqueio temporário (hold) enquanto o funcionário ou cliente finaliza a compra."""
    _liberar_holds_expirados(db, viagem_id)

    poltrona = db.get(PoltronaViagem, poltrona_viagem_id)
    if not poltrona or poltrona.viagem_id != viagem_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poltrona não encontrada")
    if poltrona.status != StatusPoltrona.LIVRE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Poltrona não está disponível")

    poltrona.status = StatusPoltrona.HOLD
    poltrona.hold_usuario_id = usuario_atual.id
    poltrona.hold_expira_em = datetime.now(timezone.utc) + timedelta(minutes=settings.seat_hold_minutes)
    db.commit()
    db.refresh(poltrona)

    return PoltronaMapaOut(
        poltrona_viagem_id=poltrona.id,
        numero=poltrona.poltrona_onibus.numero,
        andar=poltrona.poltrona_onibus.andar,
        fileira=poltrona.poltrona_onibus.fileira,
        coluna=poltrona.poltrona_onibus.coluna,
        status=poltrona.status,
        hold_expira_em=poltrona.hold_expira_em,
    )


@router.post("/{poltrona_viagem_id}/liberar", response_model=PoltronaMapaOut)
def liberar_hold(
    viagem_id: int,
    poltrona_viagem_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    poltrona = db.get(PoltronaViagem, poltrona_viagem_id)
    if not poltrona or poltrona.viagem_id != viagem_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poltrona não encontrada")
    if poltrona.status == StatusPoltrona.HOLD and poltrona.hold_usuario_id == usuario_atual.id:
        poltrona.status = StatusPoltrona.LIVRE
        poltrona.hold_expira_em = None
        poltrona.hold_usuario_id = None
        db.commit()
        db.refresh(poltrona)
    return PoltronaMapaOut(
        poltrona_viagem_id=poltrona.id,
        numero=poltrona.poltrona_onibus.numero,
        andar=poltrona.poltrona_onibus.andar,
        fileira=poltrona.poltrona_onibus.fileira,
        coluna=poltrona.poltrona_onibus.coluna,
        status=poltrona.status,
        hold_expira_em=poltrona.hold_expira_em,
    )


@router.post("/{poltrona_viagem_id}/bloquear", response_model=PoltronaMapaOut)
def bloquear_poltrona(
    viagem_id: int,
    poltrona_viagem_id: int,
    dados: BloquearPoltronaRequest,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(require_staff),
):
    """Bloqueio administrativo (manutenção, reservada para tripulação, etc.)."""
    poltrona = db.get(PoltronaViagem, poltrona_viagem_id)
    if not poltrona or poltrona.viagem_id != viagem_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poltrona não encontrada")
    if poltrona.status == StatusPoltrona.VENDIDA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Poltrona já vendida")

    poltrona.status = StatusPoltrona.BLOQUEADA
    poltrona.bloqueio_motivo = dados.motivo
    poltrona.hold_expira_em = None
    poltrona.hold_usuario_id = None
    db.commit()
    db.refresh(poltrona)
    return PoltronaMapaOut(
        poltrona_viagem_id=poltrona.id,
        numero=poltrona.poltrona_onibus.numero,
        andar=poltrona.poltrona_onibus.andar,
        fileira=poltrona.poltrona_onibus.fileira,
        coluna=poltrona.poltrona_onibus.coluna,
        status=poltrona.status,
        hold_expira_em=poltrona.hold_expira_em,
    )


@router.post("/{poltrona_viagem_id}/desbloquear", response_model=PoltronaMapaOut)
def desbloquear_poltrona(
    viagem_id: int,
    poltrona_viagem_id: int,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(require_staff),
):
    poltrona = db.get(PoltronaViagem, poltrona_viagem_id)
    if not poltrona or poltrona.viagem_id != viagem_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poltrona não encontrada")
    if poltrona.status != StatusPoltrona.BLOQUEADA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Poltrona não está bloqueada")

    poltrona.status = StatusPoltrona.LIVRE
    poltrona.bloqueio_motivo = None
    db.commit()
    db.refresh(poltrona)
    return PoltronaMapaOut(
        poltrona_viagem_id=poltrona.id,
        numero=poltrona.poltrona_onibus.numero,
        andar=poltrona.poltrona_onibus.andar,
        fileira=poltrona.poltrona_onibus.fileira,
        coluna=poltrona.poltrona_onibus.coluna,
        status=poltrona.status,
        hold_expira_em=poltrona.hold_expira_em,
    )
