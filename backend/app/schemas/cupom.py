from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TipoCupom


class CupomCreate(BaseModel):
    codigo: str = Field(min_length=3, max_length=30)
    tipo: TipoCupom
    valor: float = Field(gt=0)
    valido_ate: datetime | None = None
    max_usos: int | None = Field(default=None, gt=0)


class CupomUpdate(BaseModel):
    ativo: bool | None = None
    valido_ate: datetime | None = None
    max_usos: int | None = Field(default=None, gt=0)


class CupomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    tipo: TipoCupom
    valor: float
    ativo: bool
    valido_ate: datetime | None
    max_usos: int | None
    usos_atuais: int
    criado_em: datetime
    cliente_usuario_id: int | None = None


class AplicarCupomOut(BaseModel):
    codigo: str
    valor_desconto: float
    preco_final: float
