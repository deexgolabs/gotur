from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.database import get_db
from app.models.enums import UserRole
from app.models.rota import Rota
from app.models.usuario import Usuario
from app.schemas.rota import RotaCreate, RotaOut

router = APIRouter(prefix="/rotas", tags=["rotas"])


@router.post("", response_model=RotaOut, status_code=status.HTTP_201_CREATED)
def criar_rota(
    dados: RotaCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    rota = Rota(tenant_id=usuario_atual.tenant_id, **dados.model_dump())
    db.add(rota)
    db.commit()
    db.refresh(rota)
    return rota


@router.get("", response_model=list[RotaOut])
def listar_rotas(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA, UserRole.FUNCIONARIO)),
):
    return db.query(Rota).filter(Rota.tenant_id == usuario_atual.tenant_id).order_by(Rota.origem).all()
