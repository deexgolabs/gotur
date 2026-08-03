from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.security import hash_senha
from app.database import get_db
from app.models.enums import UserRole
from app.models.usuario import Usuario
from app.schemas.usuario import FuncionarioCreate, UsuarioOut

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.post("/funcionarios", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def criar_funcionario(
    dados: FuncionarioCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    if dados.role not in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Papel inválido para este cadastro")
    if db.query(Usuario).filter(Usuario.email == dados.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado")

    funcionario = Usuario(
        tenant_id=usuario_atual.tenant_id,
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
        role=dados.role,
        telefone=dados.telefone,
    )
    db.add(funcionario)
    db.commit()
    db.refresh(funcionario)
    return funcionario


@router.get("/funcionarios", response_model=list[UsuarioOut])
def listar_funcionarios(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    return (
        db.query(Usuario)
        .filter(Usuario.tenant_id == usuario_atual.tenant_id, Usuario.role != UserRole.CLIENTE)
        .order_by(Usuario.nome)
        .all()
    )


@router.patch("/funcionarios/{funcionario_id}/desativar", response_model=UsuarioOut)
def desativar_funcionario(
    funcionario_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    funcionario = db.get(Usuario, funcionario_id)
    if not funcionario or funcionario.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Funcionário não encontrado")
    funcionario.ativo = False
    db.commit()
    db.refresh(funcionario)
    return funcionario


@router.get("/me", response_model=UsuarioOut)
def meu_perfil(usuario_atual: Usuario = Depends(get_current_user)):
    return usuario_atual
