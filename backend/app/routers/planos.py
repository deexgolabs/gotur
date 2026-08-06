from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.database import get_db
from app.models.enums import UserRole
from app.models.plano import Plano
from app.models.usuario import Usuario
from app.schemas.plano import PlanoCreate, PlanoOut, PlanoUpdate

router = APIRouter(prefix="/planos", tags=["planos"])


@router.get("/publicos", response_model=list[PlanoOut])
def listar_planos_publicos(db: Session = Depends(get_db)):
    """Sem autenticação — usado pela página pública de cadastro de empresa."""
    return db.query(Plano).filter(Plano.ativo.is_(True)).order_by(Plano.preco_mensal).all()


@router.post("", response_model=PlanoOut, status_code=status.HTTP_201_CREATED)
def criar_plano(
    dados: PlanoCreate,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    plano = Plano(**dados.model_dump())
    db.add(plano)
    db.commit()
    db.refresh(plano)
    return plano


@router.get("", response_model=list[PlanoOut])
def listar_planos(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN_EMPRESA)),
):
    """Super admin vê todos (pra gerenciar); admin da empresa vê só os
    ativos (pra escolher/trocar o plano da própria empresa)."""
    query = db.query(Plano)
    if usuario_atual.role == UserRole.ADMIN_EMPRESA:
        query = query.filter(Plano.ativo.is_(True))
    return query.order_by(Plano.preco_mensal).all()


def _buscar_plano_ou_404(db: Session, plano_id: int) -> Plano:
    plano = db.get(Plano, plano_id)
    if not plano:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano não encontrado")
    return plano


@router.patch("/{plano_id}", response_model=PlanoOut)
def editar_plano(
    plano_id: int,
    dados: PlanoUpdate,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    plano = _buscar_plano_ou_404(db, plano_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(plano, campo, valor)
    db.commit()
    db.refresh(plano)
    return plano


@router.patch("/{plano_id}/desativar", response_model=PlanoOut)
def desativar_plano(
    plano_id: int,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    plano = _buscar_plano_ou_404(db, plano_id)
    plano.ativo = False
    db.commit()
    db.refresh(plano)
    return plano


@router.patch("/{plano_id}/ativar", response_model=PlanoOut)
def ativar_plano(
    plano_id: int,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    plano = _buscar_plano_ou_404(db, plano_id)
    plano.ativo = True
    db.commit()
    db.refresh(plano)
    return plano
