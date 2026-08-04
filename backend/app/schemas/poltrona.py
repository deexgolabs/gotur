from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import StatusPoltrona


class PoltronaMapaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    poltrona_viagem_id: int
    numero: str
    andar: int
    fileira: int
    coluna: int
    categoria: str
    preco: float
    status: StatusPoltrona
    hold_expira_em: datetime | None = None


class BloquearPoltronaRequest(BaseModel):
    motivo: str
