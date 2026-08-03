from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import UserRole


class FuncionarioCreate(BaseModel):
    nome: str
    email: EmailStr
    senha: str
    role: UserRole = UserRole.FUNCIONARIO
    telefone: str | None = None


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str
    role: UserRole
    tenant_id: int | None
    ativo: bool
