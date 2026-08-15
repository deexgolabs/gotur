from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles, require_staff
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import UserRole
from app.models.academia import Turma
from app.models.usuario import Usuario
from app.schemas.academia import TurmaCreate, TurmaOut, TurmaUpdate
from app.services.ocorrencias_turma import gerar_ocorrencias

router = APIRouter(prefix="/turmas", tags=["turmas"])


def _exigir_modulo_academia(empresa: Empresa) -> None:
    if not empresa.academia_habilitado:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="O módulo de academia não está habilitado para sua empresa")


@router.post("", response_model=TurmaOut, status_code=status.HTTP_201_CREATED)
def criar_turma(
    dados: TurmaCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    empresa = db.get(Empresa, usuario_atual.tenant_id)
    _exigir_modulo_academia(empresa)

    turma = Turma(tenant_id=usuario_atual.tenant_id, **dados.model_dump())
    db.add(turma)
    db.flush()

    gerar_ocorrencias(db, turma)

    db.commit()
    db.refresh(turma)
    return turma


@router.get("", response_model=list[TurmaOut])
def listar_turmas(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    return (
        db.query(Turma)
        .filter(Turma.tenant_id == usuario_atual.tenant_id)
        .order_by(Turma.dia_semana, Turma.hora_inicio)
        .all()
    )


def _buscar_turma_da_empresa(db: Session, turma_id: int, usuario_atual: Usuario) -> Turma:
    turma = db.get(Turma, turma_id)
    if not turma or turma.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turma não encontrada")
    return turma


@router.patch("/{turma_id}", response_model=TurmaOut)
def editar_turma(
    turma_id: int,
    dados: TurmaUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """Alterar horário/capacidade/dia da semana só afeta as próximas
    ocorrências que forem geradas — as já geradas mantêm o snapshot de
    quando foram criadas."""
    turma = _buscar_turma_da_empresa(db, turma_id, usuario_atual)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(turma, campo, valor)
    db.commit()
    db.refresh(turma)
    return turma


@router.patch("/{turma_id}/desativar", response_model=TurmaOut)
def desativar_turma(
    turma_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    turma = _buscar_turma_da_empresa(db, turma_id, usuario_atual)
    turma.ativa = False
    db.commit()
    db.refresh(turma)
    return turma


@router.get("/loja/{slug}", response_model=list[TurmaOut])
def listar_turmas_da_loja(slug: str, db: Session = Depends(get_db)):
    empresa = db.query(Empresa).filter(Empresa.slug == slug, Empresa.ativo.is_(True)).first()
    if not empresa or not empresa.academia_habilitado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja não encontrada")

    return (
        db.query(Turma)
        .filter(Turma.tenant_id == empresa.id, Turma.ativa.is_(True))
        .order_by(Turma.dia_semana, Turma.hora_inicio)
        .all()
    )
