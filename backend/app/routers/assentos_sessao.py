from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.core.deps import get_current_user, require_staff
from app.database import get_db
from app.models.enums import StatusPoltrona
from app.models.evento import AssentoSessao, Sessao
from app.models.usuario import Usuario
from app.schemas.evento import AssentoSessaoMapaOut, BloquearAssentoRequest
from app.services.auditoria import registrar as registrar_auditoria

router = APIRouter(prefix="/sessoes/{sessao_id}/assentos", tags=["assentos-sessao"])


def _get_sessao_ou_404(db: Session, sessao_id: int) -> Sessao:
    sessao = db.get(Sessao, sessao_id)
    if not sessao:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessão não encontrada")
    return sessao


def _liberar_holds_expirados(db: Session, sessao_id: int) -> None:
    """Equivalente a liberar_holds_expirados (app/services/trecho.py), mas
    sem overlap de intervalo — cada AssentoSessao tem um único status
    direto, então expirar é só voltar pra LIVRE."""
    agora = datetime.now(timezone.utc)
    expirados = (
        db.query(AssentoSessao)
        .filter(
            AssentoSessao.sessao_id == sessao_id,
            AssentoSessao.status == StatusPoltrona.HOLD,
            AssentoSessao.hold_expira_em < agora,
        )
        .all()
    )
    for assento in expirados:
        assento.status = StatusPoltrona.LIVRE
        assento.hold_usuario_id = None
        assento.hold_expira_em = None
    if expirados:
        db.commit()


def _para_mapa(assento: AssentoSessao, preco_base: float) -> AssentoSessaoMapaOut:
    return AssentoSessaoMapaOut(
        assento_sessao_id=assento.id,
        numero=assento.assento_local.numero,
        fileira=assento.assento_local.fileira,
        coluna=assento.assento_local.coluna,
        setor=assento.assento_local.setor,
        categoria=assento.assento_local.categoria,
        preco=round(preco_base * float(assento.assento_local.multiplicador_preco), 2),
        status=assento.status,
        hold_expira_em=assento.hold_expira_em,
    )


@router.get("", response_model=list[AssentoSessaoMapaOut])
def mapa_de_assentos(sessao_id: int, db: Session = Depends(get_db)):
    """Mapa público (cliente vê disponibilidade antes de logar)."""
    sessao = _get_sessao_ou_404(db, sessao_id)
    _liberar_holds_expirados(db, sessao_id)

    assentos = (
        db.query(AssentoSessao)
        .options(joinedload(AssentoSessao.assento_local))
        .filter(AssentoSessao.sessao_id == sessao_id)
        .all()
    )
    return [_para_mapa(a, float(sessao.preco)) for a in assentos]


@router.post("/{assento_sessao_id}/hold", response_model=AssentoSessaoMapaOut)
def reservar_temporariamente(
    sessao_id: int,
    assento_sessao_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    """Bloqueio temporário (hold) enquanto o funcionário ou cliente
    finaliza a compra."""
    sessao = _get_sessao_ou_404(db, sessao_id)
    _liberar_holds_expirados(db, sessao_id)

    assento = db.get(AssentoSessao, assento_sessao_id)
    if not assento or assento.sessao_id != sessao_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assento não encontrado")
    if assento.status != StatusPoltrona.LIVRE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Assento não está disponível")

    assento.status = StatusPoltrona.HOLD
    assento.hold_usuario_id = usuario_atual.id
    assento.hold_expira_em = datetime.now(timezone.utc) + timedelta(minutes=settings.seat_hold_minutes)
    db.commit()
    db.refresh(assento)
    return _para_mapa(assento, float(sessao.preco))


@router.post("/{assento_sessao_id}/liberar", response_model=AssentoSessaoMapaOut)
def liberar_hold(
    sessao_id: int,
    assento_sessao_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    sessao = _get_sessao_ou_404(db, sessao_id)
    assento = db.get(AssentoSessao, assento_sessao_id)
    if not assento or assento.sessao_id != sessao_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assento não encontrado")

    if assento.status == StatusPoltrona.HOLD and assento.hold_usuario_id == usuario_atual.id:
        assento.status = StatusPoltrona.LIVRE
        assento.hold_usuario_id = None
        assento.hold_expira_em = None
        db.commit()
        db.refresh(assento)

    return _para_mapa(assento, float(sessao.preco))


@router.post("/{assento_sessao_id}/bloquear", response_model=AssentoSessaoMapaOut)
def bloquear_assento(
    sessao_id: int,
    assento_sessao_id: int,
    dados: BloquearAssentoRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    """Bloqueio administrativo (assento com defeito, reservado etc.)."""
    sessao = _get_sessao_ou_404(db, sessao_id)
    if sessao.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessão não encontrada")
    _liberar_holds_expirados(db, sessao_id)

    assento = db.get(AssentoSessao, assento_sessao_id)
    if not assento or assento.sessao_id != sessao_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assento não encontrado")
    if assento.status == StatusPoltrona.VENDIDA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Assento já vendido")
    if assento.status == StatusPoltrona.HOLD and assento.hold_usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Assento em reserva por outro usuário")

    assento.status = StatusPoltrona.BLOQUEADA
    assento.hold_usuario_id = None
    assento.hold_expira_em = None

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="bloqueio_assento",
        entidade_tipo="assento_sessao",
        entidade_id=assento.id,
        detalhes=f"Assento {assento.assento_local.numero}: {dados.motivo}",
        tenant_id=sessao.tenant_id,
    )

    db.commit()
    db.refresh(assento)
    return _para_mapa(assento, float(sessao.preco))


@router.post("/{assento_sessao_id}/desbloquear", response_model=AssentoSessaoMapaOut)
def desbloquear_assento(
    sessao_id: int,
    assento_sessao_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    sessao = _get_sessao_ou_404(db, sessao_id)
    if sessao.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessão não encontrada")

    assento = db.get(AssentoSessao, assento_sessao_id)
    if not assento or assento.sessao_id != sessao_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assento não encontrado")
    if assento.status != StatusPoltrona.BLOQUEADA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Assento não está bloqueado")

    assento.status = StatusPoltrona.LIVRE

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="desbloqueio_assento",
        entidade_tipo="assento_sessao",
        entidade_id=assento.id,
        detalhes=f"Assento {assento.assento_local.numero}",
        tenant_id=sessao.tenant_id,
    )

    db.commit()
    db.refresh(assento)
    return _para_mapa(assento, float(sessao.preco))
