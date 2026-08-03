from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decodificar_access_token
from app.database import get_db
from app.models.enums import UserRole
from app.models.usuario import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    credenciais_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou expiradas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credenciais_invalidas

    payload = decodificar_access_token(token)
    if not payload or "sub" not in payload:
        raise credenciais_invalidas

    usuario = db.get(Usuario, int(payload["sub"]))
    if not usuario or not usuario.ativo:
        raise credenciais_invalidas
    return usuario


def require_roles(*papeis: UserRole):
    def checker(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if usuario.role not in papeis:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para executar esta ação",
            )
        return usuario

    return checker


def require_staff(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    """Funcionário, admin da empresa ou super admin (uso interno / balcão)."""
    if usuario.role not in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito à equipe da empresa")
    return usuario
