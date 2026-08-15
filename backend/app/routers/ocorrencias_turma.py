from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles, require_staff
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import StatusPassagem, UserRole
from app.models.academia import OcorrenciaTurma, ReservaAula, Turma
from app.models.usuario import Usuario
from app.schemas.academia import OcorrenciaTurmaOut, OcorrenciaTurmaUpdate

router = APIRouter(tags=["ocorrencias-turma"])


def _vagas_ocupadas(db: Session, ocorrencia_id: int) -> int:
    return (
        db.query(ReservaAula)
        .filter(ReservaAula.ocorrencia_turma_id == ocorrencia_id, ReservaAula.status == StatusPassagem.CONFIRMADA)
        .count()
    )


def _para_out(db: Session, ocorrencia: OcorrenciaTurma) -> OcorrenciaTurmaOut:
    return OcorrenciaTurmaOut(
        id=ocorrencia.id,
        turma_id=ocorrencia.turma_id,
        nome_turma=ocorrencia.turma.nome,
        data_hora_inicio=ocorrencia.data_hora_inicio,
        data_hora_fim=ocorrencia.data_hora_fim,
        capacidade_vagas=ocorrencia.capacidade_vagas,
        vagas_ocupadas=_vagas_ocupadas(db, ocorrencia.id),
        cancelada=ocorrencia.cancelada,
        preco_avulso=float(ocorrencia.turma.preco_avulso) if ocorrencia.turma.preco_avulso is not None else None,
    )


@router.get("/turmas/{turma_id}/ocorrencias", response_model=list[OcorrenciaTurmaOut])
def listar_ocorrencias_da_turma(
    turma_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    turma = db.get(Turma, turma_id)
    if not turma or turma.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turma não encontrada")

    ocorrencias = (
        db.query(OcorrenciaTurma)
        .options(joinedload(OcorrenciaTurma.turma))
        .filter(OcorrenciaTurma.turma_id == turma_id)
        .order_by(OcorrenciaTurma.data_hora_inicio)
        .all()
    )
    return [_para_out(db, o) for o in ocorrencias]


@router.get("/ocorrencias-turma", response_model=list[OcorrenciaTurmaOut])
def listar_agenda(
    de: date | None = Query(default=None),
    ate: date | None = Query(default=None),
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    query = (
        db.query(OcorrenciaTurma)
        .options(joinedload(OcorrenciaTurma.turma))
        .join(Turma)
        .filter(Turma.tenant_id == usuario_atual.tenant_id)
    )
    if de:
        query = query.filter(OcorrenciaTurma.data_hora_inicio >= datetime.combine(de, time.min))
    if ate:
        query = query.filter(OcorrenciaTurma.data_hora_inicio <= datetime.combine(ate, time.max))

    ocorrencias = query.order_by(OcorrenciaTurma.data_hora_inicio).all()
    return [_para_out(db, o) for o in ocorrencias]


def _buscar_ocorrencia_da_empresa(db: Session, ocorrencia_id: int, usuario_atual: Usuario) -> OcorrenciaTurma:
    ocorrencia = (
        db.query(OcorrenciaTurma)
        .options(joinedload(OcorrenciaTurma.turma))
        .filter(OcorrenciaTurma.id == ocorrencia_id)
        .first()
    )
    if not ocorrencia or ocorrencia.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ocorrência não encontrada")
    return ocorrencia


@router.patch("/ocorrencias-turma/{ocorrencia_id}", response_model=OcorrenciaTurmaOut)
def editar_ocorrencia(
    ocorrencia_id: int,
    dados: OcorrenciaTurmaUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """Override pontual de capacidade pra uma data específica (ex: hoje o
    instrutor só vai poder atender 10, não os 20 de sempre)."""
    ocorrencia = _buscar_ocorrencia_da_empresa(db, ocorrencia_id, usuario_atual)
    ocorrencia.capacidade_vagas = dados.capacidade_vagas
    db.commit()
    db.refresh(ocorrencia)
    return _para_out(db, ocorrencia)


@router.patch("/ocorrencias-turma/{ocorrencia_id}/cancelar", response_model=OcorrenciaTurmaOut)
def cancelar_ocorrencia(
    ocorrencia_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """Cancela a aula desse dia (feriado, instrutor doente etc.) e cancela
    as reservas confirmadas junto — não estorna pagamentos avulsos nem
    devolve aula pro pacote automaticamente, isso fica por conta do staff
    (mesmo espírito do reembolso de Ingresso, que também é manual)."""
    ocorrencia = _buscar_ocorrencia_da_empresa(db, ocorrencia_id, usuario_atual)
    ocorrencia.cancelada = True

    reservas = (
        db.query(ReservaAula)
        .filter(ReservaAula.ocorrencia_turma_id == ocorrencia.id, ReservaAula.status == StatusPassagem.CONFIRMADA)
        .all()
    )
    for reserva in reservas:
        reserva.status = StatusPassagem.CANCELADA
        reserva.cancelada_em = datetime.utcnow()

    db.commit()
    db.refresh(ocorrencia)
    return _para_out(db, ocorrencia)


@router.get("/ocorrencias-turma/loja/{slug}", response_model=list[OcorrenciaTurmaOut])
def listar_ocorrencias_da_loja(slug: str, db: Session = Depends(get_db)):
    empresa = db.query(Empresa).filter(Empresa.slug == slug, Empresa.ativo.is_(True)).first()
    if not empresa or not empresa.academia_habilitado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja não encontrada")

    ocorrencias = (
        db.query(OcorrenciaTurma)
        .options(joinedload(OcorrenciaTurma.turma))
        .join(Turma)
        .filter(
            Turma.tenant_id == empresa.id,
            OcorrenciaTurma.cancelada.is_(False),
            OcorrenciaTurma.data_hora_inicio >= datetime.utcnow(),
        )
        .order_by(OcorrenciaTurma.data_hora_inicio)
        .all()
    )
    return [_para_out(db, o) for o in ocorrencias]
