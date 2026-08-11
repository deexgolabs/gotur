from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import TipoViagemJornada


class IniciarJornadaRequest(BaseModel):
    motorista_nome: str
    tipo_viagem: TipoViagemJornada
    referencia_id: int


class JornadaMotoristaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    motorista_nome: str
    tipo_viagem: TipoViagemJornada
    referencia_id: int
    inicio: datetime
    fim: datetime | None
    horas: float
    criado_em: datetime


class ResumoJornadaOut(BaseModel):
    horas_ultimas_24h: float
    acima_do_limite: bool
