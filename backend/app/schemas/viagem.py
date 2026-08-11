from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.onibus import OnibusOut
from app.schemas.rota import RotaOut


class ViagemCreate(BaseModel):
    rota_id: int
    onibus_id: int
    data_hora_partida: datetime
    preco: float
    motorista_nome: str | None = None


class ViagemUpdate(BaseModel):
    data_hora_partida: datetime | None = None
    preco: float | None = None
    motorista_nome: str | None = None


class ViagemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    data_hora_partida: datetime
    preco: float
    ativo: bool
    motorista_nome: str | None = None
    rota: RotaOut
    onibus: OnibusOut


class ViagemBuscaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    empresa_nome: str
    data_hora_partida: datetime
    preco: float
    origem: str
    destino: str
    parada_origem_id: int
    parada_destino_id: int
    poltronas_livres: int
