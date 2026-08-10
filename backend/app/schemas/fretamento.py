from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import StatusFretamento


class FretamentoCreate(BaseModel):
    cliente_nome: str
    cliente_documento: str | None = None
    cliente_contato: str | None = None
    origem: str
    destino: str
    data_hora_saida: datetime
    data_hora_retorno_prevista: datetime | None = None
    onibus_id: int | None = None
    motorista_nome: str | None = None
    distancia_km: float | None = Field(default=None, ge=0)
    valor_por_km: float | None = Field(default=None, ge=0)
    valor_total: float | None = Field(default=None, ge=0)
    observacoes: str | None = None


class FretamentoUpdate(BaseModel):
    cliente_nome: str | None = None
    cliente_documento: str | None = None
    cliente_contato: str | None = None
    origem: str | None = None
    destino: str | None = None
    data_hora_saida: datetime | None = None
    data_hora_retorno_prevista: datetime | None = None
    onibus_id: int | None = None
    motorista_nome: str | None = None
    distancia_km: float | None = Field(default=None, ge=0)
    valor_por_km: float | None = Field(default=None, ge=0)
    valor_total: float | None = Field(default=None, ge=0)
    observacoes: str | None = None


class MudarStatusFretamentoRequest(BaseModel):
    status: StatusFretamento


class PosicaoCreate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class PosicaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    latitude: float
    longitude: float
    registrado_em: datetime


class FretamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo_rastreio: str
    cliente_nome: str
    cliente_documento: str | None
    cliente_contato: str | None
    origem: str
    destino: str
    data_hora_saida: datetime
    data_hora_retorno_prevista: datetime | None
    onibus_id: int | None
    onibus_identificacao: str | None = None
    motorista_nome: str | None
    distancia_km: float | None
    valor_por_km: float | None
    valor_total: float | None
    status: StatusFretamento
    observacoes: str | None
    criado_em: datetime
    distancia_percorrida_km: float = 0.0
    ultima_posicao: PosicaoOut | None = None


class RastreioPublicoOut(BaseModel):
    codigo_rastreio: str
    cliente_nome: str
    origem: str
    destino: str
    data_hora_saida: datetime
    status: StatusFretamento
    distancia_percorrida_km: float
    ultima_posicao: PosicaoOut | None
    trajeto: list[PosicaoOut]
