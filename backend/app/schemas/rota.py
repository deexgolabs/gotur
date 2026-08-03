from pydantic import BaseModel, ConfigDict


class RotaCreate(BaseModel):
    origem: str
    destino: str


class RotaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    origem: str
    destino: str
    ativo: bool
