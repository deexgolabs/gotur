from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles
from app.database import get_db
from app.models.enums import UserRole
from app.models.parada import Parada
from app.models.rota import Rota
from app.models.usuario import Usuario
from app.schemas.rota import RotaCreate, RotaOut, RotaUpdate

router = APIRouter(prefix="/rotas", tags=["rotas"])


@router.post("", response_model=RotaOut, status_code=status.HTTP_201_CREATED)
def criar_rota(
    dados: RotaCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    rota = Rota(tenant_id=usuario_atual.tenant_id, origem=dados.origem, destino=dados.destino)
    db.add(rota)
    db.flush()

    pontos = dados.paradas or [
        {"nome": dados.origem, "peso_proximo": 1.0},
        {"nome": dados.destino, "peso_proximo": None},
    ]
    for ordem, ponto in enumerate(pontos):
        nome = ponto["nome"] if isinstance(ponto, dict) else ponto.nome
        peso = ponto["peso_proximo"] if isinstance(ponto, dict) else ponto.peso_proximo
        db.add(Parada(rota_id=rota.id, nome=nome, ordem=ordem, peso_proximo=None if ordem == len(pontos) - 1 else peso))

    db.commit()
    db.refresh(rota)
    return rota


@router.get("", response_model=list[RotaOut])
def listar_rotas(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA, UserRole.FUNCIONARIO)),
):
    return (
        db.query(Rota)
        .options(joinedload(Rota.paradas))
        .filter(Rota.tenant_id == usuario_atual.tenant_id)
        .order_by(Rota.origem)
        .all()
    )


def _buscar_rota_da_empresa(db: Session, rota_id: int, usuario_atual: Usuario) -> Rota:
    rota = db.get(Rota, rota_id)
    if not rota or rota.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rota não encontrada")
    return rota


@router.patch("/{rota_id}", response_model=RotaOut)
def editar_rota(
    rota_id: int,
    dados: RotaUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    rota = _buscar_rota_da_empresa(db, rota_id, usuario_atual)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(rota, campo, valor)
    db.commit()
    db.refresh(rota)
    return rota


@router.patch("/{rota_id}/desativar", response_model=RotaOut)
def desativar_rota(
    rota_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    rota = _buscar_rota_da_empresa(db, rota_id, usuario_atual)
    rota.ativo = False
    db.commit()
    db.refresh(rota)
    return rota


@router.patch("/{rota_id}/ativar", response_model=RotaOut)
def ativar_rota(
    rota_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    rota = _buscar_rota_da_empresa(db, rota_id, usuario_atual)
    rota.ativo = True
    db.commit()
    db.refresh(rota)
    return rota
