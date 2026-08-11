from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.database import get_db
from app.models.cupom import Cupom
from app.models.enums import UserRole
from app.models.usuario import Usuario
from app.schemas.cupom import CupomCreate, CupomOut, CupomUpdate

router = APIRouter(prefix="/cupons", tags=["cupons"])


@router.post("", response_model=CupomOut, status_code=status.HTTP_201_CREATED)
def criar_cupom(
    dados: CupomCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    codigo = dados.codigo.strip().upper()
    existente = db.query(Cupom).filter(Cupom.tenant_id == usuario_atual.tenant_id, Cupom.codigo == codigo).first()
    if existente:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Já existe um cupom com esse código")

    cupom = Cupom(
        tenant_id=usuario_atual.tenant_id,
        codigo=codigo,
        tipo=dados.tipo,
        valor=dados.valor,
        valido_ate=dados.valido_ate,
        max_usos=dados.max_usos,
    )
    db.add(cupom)
    db.commit()
    db.refresh(cupom)
    return cupom


@router.get("", response_model=list[CupomOut])
def listar_cupons(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA, UserRole.FUNCIONARIO)),
):
    return (
        db.query(Cupom)
        .filter(Cupom.tenant_id == usuario_atual.tenant_id)
        .order_by(Cupom.criado_em.desc())
        .all()
    )


def _buscar_cupom_da_empresa(db: Session, cupom_id: int, usuario_atual: Usuario) -> Cupom:
    cupom = db.get(Cupom, cupom_id)
    if not cupom or cupom.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cupom não encontrado")
    return cupom


@router.get("/minhas", response_model=list[CupomOut])
def meus_cupons_de_fidelidade(
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.CLIENTE)),
):
    """Cupons pessoais que o cliente ganhou pelo programa de fidelidade —
    não inclui cupons gerais (esses o cliente já vê/usa direto pelo
    código, sem precisar listar). `tenant_id` opcional: usado pela loja
    white-label pra mostrar só os cupons daquela empresa; sem ele, mostra
    de todas (portal genérico do cliente), igual /passagens/minhas."""
    query = db.query(Cupom).filter(Cupom.cliente_usuario_id == usuario_atual.id, Cupom.ativo.is_(True))
    if tenant_id is not None:
        query = query.filter(Cupom.tenant_id == tenant_id)
    return query.order_by(Cupom.criado_em.desc()).all()


@router.patch("/{cupom_id}", response_model=CupomOut)
def editar_cupom(
    cupom_id: int,
    dados: CupomUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    cupom = _buscar_cupom_da_empresa(db, cupom_id, usuario_atual)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(cupom, campo, valor)
    db.commit()
    db.refresh(cupom)
    return cupom
