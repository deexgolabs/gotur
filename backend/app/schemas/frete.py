from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import StatusFrete
from app.schemas.fretamento import PosicaoOut


class FreteCreate(BaseModel):
    remetente_nome: str
    remetente_contato: str | None = None
    destinatario_nome: str
    destinatario_contato: str | None = None
    descricao_carga: str | None = None
    origem: str
    destino: str
    data_hora_coleta: datetime
    data_hora_entrega_prevista: datetime | None = None
    motorista_nome: str | None = None
    motorista_id: int | None = None
    veiculo_descricao: str | None = None
    icone_mapa: str | None = None
    distancia_km: float | None = Field(default=None, ge=0)
    valor_por_km: float | None = Field(default=None, ge=0)
    valor_total: float | None = Field(default=None, ge=0)
    peso_kg: float | None = Field(default=None, ge=0)
    quantidade_volumes: int | None = Field(default=None, ge=0)
    valor_declarado: float | None = Field(default=None, ge=0)
    parceiro_id: int | None = None
    observacoes: str | None = None


class SolicitarFreteRequest(BaseModel):
    """Formulário público da loja white-label — só os dados que o próprio
    remetente sabe informar. Preço, motorista e veículo ficam por conta da
    empresa depois, ao confirmar o frete."""

    remetente_nome: str
    remetente_contato: str
    destinatario_nome: str
    destinatario_contato: str | None = None
    descricao_carga: str | None = None
    origem: str
    destino: str
    data_hora_coleta: datetime
    peso_kg: float | None = Field(default=None, ge=0)
    quantidade_volumes: int | None = Field(default=None, ge=0)
    valor_declarado: float | None = Field(default=None, ge=0)
    observacoes: str | None = None


class FreteUpdate(BaseModel):
    remetente_nome: str | None = None
    remetente_contato: str | None = None
    destinatario_nome: str | None = None
    destinatario_contato: str | None = None
    descricao_carga: str | None = None
    origem: str | None = None
    destino: str | None = None
    data_hora_coleta: datetime | None = None
    data_hora_entrega_prevista: datetime | None = None
    motorista_nome: str | None = None
    motorista_id: int | None = None
    veiculo_descricao: str | None = None
    distancia_km: float | None = Field(default=None, ge=0)
    valor_por_km: float | None = Field(default=None, ge=0)
    valor_total: float | None = Field(default=None, ge=0)
    peso_kg: float | None = Field(default=None, ge=0)
    quantidade_volumes: int | None = Field(default=None, ge=0)
    valor_declarado: float | None = Field(default=None, ge=0)
    parceiro_id: int | None = None
    observacoes: str | None = None
    icone_mapa: str | None = None


class MudarStatusFreteRequest(BaseModel):
    status: StatusFrete


class FreteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo_rastreio: str
    remetente_nome: str
    remetente_contato: str | None
    destinatario_nome: str
    destinatario_contato: str | None
    descricao_carga: str | None
    origem: str
    destino: str
    data_hora_coleta: datetime
    data_hora_entrega_prevista: datetime | None
    motorista_nome: str | None
    motorista_id: int | None = None
    veiculo_descricao: str | None
    distancia_km: float | None
    valor_por_km: float | None
    valor_total: float | None
    peso_kg: float | None = None
    quantidade_volumes: int | None = None
    valor_declarado: float | None = None
    parceiro_id: int | None = None
    status: StatusFrete
    icone_mapa: str = "🚚"
    observacoes: str | None
    criado_em: datetime
    distancia_percorrida_km: float = 0.0
    ultima_posicao: PosicaoOut | None = None


class RastreioFretePublicoOut(BaseModel):
    codigo_rastreio: str
    remetente_nome: str
    destinatario_nome: str
    origem: str
    destino: str
    data_hora_coleta: datetime
    status: StatusFrete
    icone_mapa: str = "🚚"
    distancia_percorrida_km: float
    ultima_posicao: PosicaoOut | None
    trajeto: list[PosicaoOut]
