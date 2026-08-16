from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import UserRole
from app.models.evento import AssentoLocal, Local
from app.models.usuario import Usuario
from app.schemas.evento import AssentoLocalOut, AssentoLocalUpdate, LocalCreate, LocalOut, LocalUpdate
from app.services.limites_plano import verificar_limite_locais

router = APIRouter(prefix="/locais", tags=["locais"])


def _gerar_layout_automatico(total: int) -> list[dict]:
    """Layout 2+corredor+2 por fileira — mesmo padrão de app/routers/onibus.py."""
    layout = []
    numero = 1
    fileira = 1
    while numero <= total:
        for coluna in range(1, 5):
            if numero > total:
                break
            layout.append({"numero": str(numero), "fileira": fileira, "coluna": coluna})
            numero += 1
        fileira += 1
    return layout


def _exigir_modulo_eventos(empresa: Empresa) -> None:
    if not empresa.eventos_habilitado:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="O módulo de eventos não está habilitado para sua empresa")


@router.post("", response_model=LocalOut, status_code=status.HTTP_201_CREATED)
def criar_local(
    dados: LocalCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    empresa = db.get(Empresa, usuario_atual.tenant_id)
    _exigir_modulo_eventos(empresa)
    verificar_limite_locais(db, empresa)

    if dados.assentos:
        layout = [a.model_dump() for a in dados.assentos]
    else:
        if not dados.total_assentos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Informe `assentos` ou `total_assentos` para gerar o layout",
            )
        layout = _gerar_layout_automatico(dados.total_assentos)

    local = Local(tenant_id=usuario_atual.tenant_id, nome=dados.nome, endereco=dados.endereco)
    db.add(local)
    db.flush()

    for item in layout:
        db.add(AssentoLocal(local_id=local.id, **item))

    db.commit()
    db.refresh(local)
    return local


@router.get("", response_model=list[LocalOut])
def listar_locais(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA, UserRole.FUNCIONARIO)),
):
    return (
        db.query(Local)
        .options(joinedload(Local.assentos))
        .filter(Local.tenant_id == usuario_atual.tenant_id)
        .order_by(Local.nome)
        .all()
    )


def _buscar_local_da_empresa(db: Session, local_id: int, usuario_atual: Usuario) -> Local:
    local = db.get(Local, local_id)
    if not local or local.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local não encontrado")
    return local


@router.patch("/{local_id}", response_model=LocalOut)
def editar_local(
    local_id: int,
    dados: LocalUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    local = _buscar_local_da_empresa(db, local_id, usuario_atual)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(local, campo, valor)
    db.commit()
    db.refresh(local)
    return local


@router.patch("/{local_id}/desativar", response_model=LocalOut)
def desativar_local(
    local_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    local = _buscar_local_da_empresa(db, local_id, usuario_atual)
    local.ativo = False
    db.commit()
    db.refresh(local)
    return local


@router.patch("/{local_id}/ativar", response_model=LocalOut)
def ativar_local(
    local_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    local = _buscar_local_da_empresa(db, local_id, usuario_atual)
    local.ativo = True
    db.commit()
    db.refresh(local)
    return local


@router.patch("/{local_id}/assentos/{assento_id}", response_model=AssentoLocalOut)
def editar_categoria_assento(
    local_id: int,
    assento_id: int,
    dados: AssentoLocalUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """Define categoria/multiplicador de preço de um assento (ex: 'vip'
    com multiplicador 2.0 = o dobro do preço base da sessão)."""
    _buscar_local_da_empresa(db, local_id, usuario_atual)
    assento = db.get(AssentoLocal, assento_id)
    if not assento or assento.local_id != local_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assento não encontrado")

    assento.categoria = dados.categoria
    assento.multiplicador_preco = dados.multiplicador_preco
    db.commit()
    db.refresh(assento)
    return assento
