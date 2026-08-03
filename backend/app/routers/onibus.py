from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles
from app.database import get_db
from app.models.enums import UserRole
from app.models.onibus import Onibus, PoltronaOnibus
from app.models.usuario import Usuario
from app.schemas.onibus import OnibusCreate, OnibusOut

router = APIRouter(prefix="/onibus", tags=["onibus"])


def _gerar_layout_automatico(total: int) -> list[dict]:
    """Layout 2+2 (dois assentos, corredor, dois assentos) por fileira."""
    layout = []
    numero = 1
    fileira = 1
    while numero <= total:
        for coluna in range(1, 5):
            if numero > total:
                break
            layout.append({"numero": str(numero), "andar": 1, "fileira": fileira, "coluna": coluna})
            numero += 1
        fileira += 1
    return layout


@router.post("", response_model=OnibusOut, status_code=status.HTTP_201_CREATED)
def criar_onibus(
    dados: OnibusCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    if dados.poltronas:
        layout = [p.model_dump() for p in dados.poltronas]
    else:
        if not dados.total_poltronas:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Informe `poltronas` ou `total_poltronas` para gerar o layout",
            )
        layout = _gerar_layout_automatico(dados.total_poltronas)

    onibus = Onibus(tenant_id=usuario_atual.tenant_id, identificacao=dados.identificacao, tipo=dados.tipo)
    db.add(onibus)
    db.flush()

    for item in layout:
        db.add(PoltronaOnibus(onibus_id=onibus.id, **item))

    db.commit()
    db.refresh(onibus)
    return onibus


@router.get("", response_model=list[OnibusOut])
def listar_onibus(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA, UserRole.FUNCIONARIO)),
):
    return (
        db.query(Onibus)
        .options(joinedload(Onibus.poltronas))
        .filter(Onibus.tenant_id == usuario_atual.tenant_id)
        .order_by(Onibus.identificacao)
        .all()
    )
