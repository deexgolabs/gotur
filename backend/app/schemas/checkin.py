from datetime import datetime

from pydantic import BaseModel


class CheckinConsultaOut(BaseModel):
    passagem_id: int
    localizador: str
    cliente_nome: str
    numero_poltrona: str
    origem: str
    destino: str
    data_hora_partida: datetime
    status_passagem: str
    checkin_em: datetime | None = None
