from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.core.security import hash_senha
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import UserRole
from app.models.usuario import Usuario
from app.schemas.empresa import EmpresaCreate, EmpresaOut
from app.schemas.usuario import FuncionarioCreate, UsuarioOut

router = APIRouter(prefix="/empresas", tags=["empresas"])


@router.post("", response_model=EmpresaOut, status_code=status.HTTP_201_CREATED)
def criar_empresa(
    dados: EmpresaCreate,
    db: Session = Depends(get_db),
    _usuario=Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    if db.query(Empresa).filter(Empresa.cnpj == dados.cnpj).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CNPJ já cadastrado")
    empresa = Empresa(**dados.model_dump())
    db.add(empresa)
    db.commit()
    db.refresh(empresa)
    return empresa


@router.get("", response_model=list[EmpresaOut])
def listar_empresas(
    db: Session = Depends(get_db),
    _usuario=Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    return db.query(Empresa).order_by(Empresa.nome).all()


@router.post("/{empresa_id}/admin", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def criar_admin_empresa(
    empresa_id: int,
    dados: FuncionarioCreate,
    db: Session = Depends(get_db),
    _usuario=Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    empresa = db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa não encontrada")
    if db.query(Usuario).filter(Usuario.email == dados.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado")

    usuario = Usuario(
        tenant_id=empresa.id,
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
        role=UserRole.ADMIN_EMPRESA,
        telefone=dados.telefone,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario
