from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import TipoViagemJornada


class ChecklistViagemCreate(BaseModel):
    motorista_nome: str
    tipo_viagem: TipoViagemJornada
    referencia_id: int
    pneus_ok: bool = False
    oleo_ok: bool = False
    combustivel_ok: bool = False
    observacoes: str | None = None


class ChecklistViagemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    motorista_nome: str
    tipo_viagem: TipoViagemJornada
    referencia_id: int
    pneus_ok: bool
    oleo_ok: bool
    combustivel_ok: bool
    observacoes: str | None
    criado_em: datetime
