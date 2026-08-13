from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import UserRole


class FuncionarioCreate(BaseModel):
    nome: str
    email: EmailStr
    senha: str
    role: UserRole = UserRole.FUNCIONARIO
    telefone: str | None = None


class TrocarSenhaRequest(BaseModel):
    senha_atual: str
    senha_nova: str


class AtualizarPerfilRequest(BaseModel):
    telefone: str | None = None


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str
    role: UserRole
    tenant_id: int | None
    ativo: bool
    telefone: str | None = None
    codigo_indicacao: str | None = None
