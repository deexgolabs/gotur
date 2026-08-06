from pydantic import BaseModel, ConfigDict


class PlanoCreate(BaseModel):
    nome: str
    descricao: str | None = None
    preco_mensal: float
    max_onibus: int | None = None
    max_funcionarios: int | None = None
    max_viagens_mes: int | None = None


class PlanoUpdate(BaseModel):
    nome: str | None = None
    descricao: str | None = None
    preco_mensal: float | None = None
    max_onibus: int | None = None
    max_funcionarios: int | None = None
    max_viagens_mes: int | None = None


class PlanoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    descricao: str | None
    preco_mensal: float
    max_onibus: int | None
    max_funcionarios: int | None
    max_viagens_mes: int | None
    ativo: bool
