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


class CheckinEventoConsultaOut(BaseModel):
    ingresso_id: int
    codigo: str
    cliente_nome: str
    numero_assento: str
    nome_evento: str
    local_nome: str
    data_hora: datetime
    status_ingresso: str
    checkin_em: datetime | None = None
