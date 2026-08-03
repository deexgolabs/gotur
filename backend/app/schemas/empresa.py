from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EmpresaCreate(BaseModel):
    nome: str
    cnpj: str
    email_contato: str | None = None


class EmpresaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    cnpj: str
    email_contato: str | None
    ativo: bool
    criado_em: datetime
