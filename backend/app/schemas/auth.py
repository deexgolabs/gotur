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


class RegistroEmpresa(BaseModel):
    empresa_nome: str
    cnpj: str
    empresa_email: EmailStr | None = None
    plano_id: int
    admin_nome: str
    admin_email: EmailStr
    admin_senha: str
    admin_telefone: str | None = None
