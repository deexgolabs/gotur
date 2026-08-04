from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReembolsarRequest(BaseModel):
    motivo: str
    valor: float | None = None  # None = reembolso integral do valor pago


class ReembolsoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    passagem_id: int
    valor_pago: float
    valor_reembolsado: float
    motivo_reembolso: str
    reembolsado_em: datetime
