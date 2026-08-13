from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

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
    tem_acesso: bool = False


class CriarAcessoMotoristaRequest(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=6)


class TrajetoMotoristaOut(BaseModel):
    """Item genérico da agenda do motorista — cobre viagem, fretamento e
    frete com o mesmo formato, pra a tela dele não precisar saber a
    diferença entre os três."""

    tipo: str  # "viagem" | "fretamento" | "frete"
    id: int
    origem: str
    destino: str
    data_hora: datetime
    status: str
