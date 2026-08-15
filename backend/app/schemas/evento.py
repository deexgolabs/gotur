from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import StatusPoltrona


class AssentoLocalLayout(BaseModel):
    numero: str
    fileira: int
    coluna: int
    setor: str | None = None
    categoria: str = "padrao"
    multiplicador_preco: float = 1.00


class LocalCreate(BaseModel):
    nome: str
    endereco: str | None = None
    assentos: list[AssentoLocalLayout] = Field(default_factory=list)
    total_assentos: int | None = Field(
        default=None,
        description="Se `assentos` não for informado, gera automaticamente um layout 2+corredor+2 com esse total.",
    )


class LocalUpdate(BaseModel):
    nome: str | None = None
    endereco: str | None = None


class AssentoLocalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero: str
    fileira: int
    coluna: int
    setor: str | None = None
    categoria: str
    multiplicador_preco: float


class AssentoLocalUpdate(BaseModel):
    categoria: str
    multiplicador_preco: float = Field(gt=0, le=10)


class LocalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    endereco: str | None = None
    ativo: bool
    assentos: list[AssentoLocalOut] = Field(default_factory=list)


class SessaoCreate(BaseModel):
    local_id: int
    nome_evento: str
    data_hora: datetime
    preco: float


class SessaoUpdate(BaseModel):
    nome_evento: str | None = None
    data_hora: datetime | None = None
    preco: float | None = None


class SessaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    nome_evento: str
    data_hora: datetime
    preco: float
    ativo: bool
    local: LocalOut


class SessaoLojaOut(BaseModel):
    """Sessão futura pra listagem pública da loja — não tem busca por
    origem/destino como passagem, é "o que vai passar"."""

    id: int
    nome_evento: str
    local_nome: str
    data_hora: datetime
    preco: float
    assentos_livres: int


class AssentoSessaoMapaOut(BaseModel):
    assento_sessao_id: int
    numero: str
    fileira: int
    coluna: int
    setor: str | None = None
    categoria: str
    preco: float
    status: StatusPoltrona
    hold_expira_em: datetime | None = None


class BloquearAssentoRequest(BaseModel):
    motivo: str
