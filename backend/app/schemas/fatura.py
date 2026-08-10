from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import StatusFatura


class FaturaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    empresa_id: int
    empresa_nome: str | None = None
    plano_id: int
    plano_nome: str | None = None
    valor: float
    status: StatusFatura
    vencimento: date
    pago_em: datetime | None
    criado_em: datetime
    pix_copia_cola: str | None = None
    pix_expira_em: datetime | None = None
