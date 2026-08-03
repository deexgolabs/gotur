from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import criar_access_token, hash_senha, verificar_senha
from app.database import get_db
from app.models.enums import UserRole
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequest, RegistroCliente, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(dados: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == dados.email).first()
    if not usuario or not verificar_senha(dados.senha, usuario.senha_hash) or not usuario.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos")

    token = criar_access_token(
        {"sub": str(usuario.id), "role": usuario.role.value, "tenant_id": usuario.tenant_id}
    )
    return TokenResponse(
        access_token=token, role=usuario.role, nome=usuario.nome, tenant_id=usuario.tenant_id
    )


@router.post("/registrar-cliente", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def registrar_cliente(dados: RegistroCliente, db: Session = Depends(get_db)):
    if db.query(Usuario).filter(Usuario.email == dados.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado")

    usuario = Usuario(
        tenant_id=None,
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
        role=UserRole.CLIENTE,
        documento=dados.documento,
        telefone=dados.telefone,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    token = criar_access_token(
        {"sub": str(usuario.id), "role": usuario.role.value, "tenant_id": usuario.tenant_id}
    )
    return TokenResponse(
        access_token=token, role=usuario.role, nome=usuario.nome, tenant_id=usuario.tenant_id
    )
