from pydantic import BaseModel, EmailStr

from app.models.enums import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    nome: str
    tenant_id: int | None = None


class RegistroCliente(BaseModel):
    nome: str
    email: EmailStr
    senha: str
    documento: str
    telefone: str | None = None
