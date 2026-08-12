from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.database import get_db
from app.models.enums import UserRole
from app.models.motorista import Motorista
from app.models.usuario import Usuario
from app.schemas.motorista import MotoristaCreate, MotoristaOut, MotoristaUpdate

router = APIRouter(prefix="/motoristas", tags=["motoristas"])


@router.post("", response_model=MotoristaOut, status_code=status.HTTP_201_CREATED)
def criar_motorista(
    dados: MotoristaCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    motorista = Motorista(tenant_id=usuario_atual.tenant_id, **dados.model_dump())
    db.add(motorista)
    db.commit()
    db.refresh(motorista)
    return motorista


@router.get("", response_model=list[MotoristaOut])
def listar_motoristas(
    apenas_ativos: bool = False,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA, UserRole.FUNCIONARIO)),
):
    """`apenas_ativos=true` é usado pelos formulários de viagem/fretamento/
    frete pra popular o seletor de motorista (sem mostrar os desativados)."""
    query = db.query(Motorista).filter(Motorista.tenant_id == usuario_atual.tenant_id)
    if apenas_ativos:
        query = query.filter(Motorista.ativo.is_(True))
    return query.order_by(Motorista.nome).all()


def _buscar_motorista_da_empresa(db: Session, motorista_id: int, usuario_atual: Usuario) -> Motorista:
    motorista = db.get(Motorista, motorista_id)
    if not motorista or motorista.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Motorista não encontrado")
    return motorista


@router.patch("/{motorista_id}", response_model=MotoristaOut)
def editar_motorista(
    motorista_id: int,
    dados: MotoristaUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    motorista = _buscar_motorista_da_empresa(db, motorista_id, usuario_atual)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(motorista, campo, valor)
    db.commit()
    db.refresh(motorista)
    return motorista
