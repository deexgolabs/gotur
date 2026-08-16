from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def normalizar_email(email: str) -> str:
    """E-mail não é case-sensitive na prática (Gmail, Outlook etc. tratam
    maiúscula/minúscula como iguais), mas a comparação `==` no banco é.
    Sem isso, um cliente cadastrado como "Fulano@Live.com" não é achado
    depois por um staff digitando "fulano@live.com" — mesma conta, e a
    busca falha silenciosamente com "não encontrado"."""
    return email.strip().lower()


def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha, senha_hash)


def criar_access_token(dados: dict) -> str:
    to_encode = dados.copy()
    expira = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode["exp"] = expira
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decodificar_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
