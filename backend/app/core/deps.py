from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decodificar_access_token
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import StatusAssinatura, UserRole
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


def _verificar_empresa_liberada(usuario: Usuario, db: Session) -> None:
    """Bloqueia ações operacionais (não login/faturas) de funcionário/admin
    de uma empresa suspensa por falta de pagamento da assinatura."""
    if usuario.role not in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA) or not usuario.tenant_id:
        return
    empresa = db.get(Empresa, usuario.tenant_id)
    if not empresa or not empresa.ativo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Empresa desativada. Fale com o suporte.")
    if empresa.status_assinatura == StatusAssinatura.SUSPENSA:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Assinatura da empresa suspensa por falta de pagamento. Acesse Faturas para regularizar.",
        )


def require_roles(*papeis: UserRole):
    def checker(usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> Usuario:
        if usuario.role not in papeis:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para executar esta ação",
            )
        _verificar_empresa_liberada(usuario, db)
        return usuario

    return checker


def require_staff(usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> Usuario:
    """Funcionário, admin da empresa ou super admin (uso interno / balcão)."""
    if usuario.role not in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito à equipe da empresa")
    _verificar_empresa_liberada(usuario, db)
    return usuario
