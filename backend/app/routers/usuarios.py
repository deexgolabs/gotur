from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.security import hash_senha, verificar_senha
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import UserRole
from app.models.usuario import Usuario
from app.schemas.usuario import AtualizarPerfilRequest, FuncionarioCreate, TrocarSenhaRequest, UsuarioOut
from app.services.limites_plano import verificar_limite_funcionarios

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

    empresa = db.get(Empresa, usuario_atual.tenant_id)
    verificar_limite_funcionarios(db, empresa)

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


@router.patch("/me", response_model=UsuarioOut)
def atualizar_meu_perfil(
    dados: AtualizarPerfilRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(usuario_atual, campo, valor)
    db.commit()
    db.refresh(usuario_atual)
    return usuario_atual


@router.post("/me/senha", status_code=status.HTTP_204_NO_CONTENT)
def trocar_minha_senha(
    dados: TrocarSenhaRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    if not verificar_senha(dados.senha_atual, usuario_atual.senha_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha atual incorreta")
    if len(dados.senha_nova) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A nova senha deve ter ao menos 6 caracteres")

    usuario_atual.senha_hash = hash_senha(dados.senha_nova)
    db.commit()
