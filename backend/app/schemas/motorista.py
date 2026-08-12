from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import CategoriaCNH


class MotoristaCreate(BaseModel):
    nome: str
    cnh: str | None = None
    categoria_cnh: CategoriaCNH | None = None
    telefone: str | None = None


class MotoristaUpdate(BaseModel):
    nome: str | None = None
    cnh: str | None = None
    categoria_cnh: CategoriaCNH | None = None
    telefone: str | None = None
    ativo: bool | None = None


class MotoristaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    cnh: str | None
    categoria_cnh: CategoriaCNH | None
    telefone: str | None
    ativo: bool
    criado_em: datetime
