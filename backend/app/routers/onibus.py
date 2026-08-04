from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles
from app.database import get_db
from app.models.enums import UserRole
from app.models.onibus import Onibus, PoltronaOnibus
from app.models.usuario import Usuario
from app.schemas.onibus import OnibusCreate, OnibusOut, OnibusUpdate, PoltronaOnibusOut, PoltronaOnibusUpdate

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


def _buscar_onibus_da_empresa(db: Session, onibus_id: int, usuario_atual: Usuario) -> Onibus:
    onibus = db.get(Onibus, onibus_id)
    if not onibus or onibus.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ônibus não encontrado")
    return onibus


@router.patch("/{onibus_id}", response_model=OnibusOut)
def editar_onibus(
    onibus_id: int,
    dados: OnibusUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """Edita identificação/tipo. A disposição física do layout (número,
    fileira, coluna) não é editável depois de criado, pois viagens já podem
    referenciar as poltronas existentes — categoria/preço de cada poltrona
    são editáveis via `/onibus/{id}/poltronas/{poltrona_id}`."""
    onibus = _buscar_onibus_da_empresa(db, onibus_id, usuario_atual)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(onibus, campo, valor)
    db.commit()
    db.refresh(onibus)
    return onibus


@router.patch("/{onibus_id}/desativar", response_model=OnibusOut)
def desativar_onibus(
    onibus_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    onibus = _buscar_onibus_da_empresa(db, onibus_id, usuario_atual)
    onibus.ativo = False
    db.commit()
    db.refresh(onibus)
    return onibus


@router.patch("/{onibus_id}/ativar", response_model=OnibusOut)
def ativar_onibus(
    onibus_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    onibus = _buscar_onibus_da_empresa(db, onibus_id, usuario_atual)
    onibus.ativo = True
    db.commit()
    db.refresh(onibus)
    return onibus


@router.patch("/{onibus_id}/poltronas/{poltrona_id}", response_model=PoltronaOnibusOut)
def editar_categoria_poltrona(
    onibus_id: int,
    poltrona_id: int,
    dados: PoltronaOnibusUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """Define a categoria e o multiplicador de preço de uma poltrona (ex:
    'executiva' com multiplicador 1.5 = 50% mais cara que o preço base da
    viagem)."""
    _buscar_onibus_da_empresa(db, onibus_id, usuario_atual)
    poltrona = db.get(PoltronaOnibus, poltrona_id)
    if not poltrona or poltrona.onibus_id != onibus_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poltrona não encontrada")

    poltrona.categoria = dados.categoria
    poltrona.multiplicador_preco = dados.multiplicador_preco
    db.commit()
    db.refresh(poltrona)
    return poltrona
