from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TipoDocumentoOnibus, TipoOnibus


class DocumentoOnibusCreate(BaseModel):
    tipo: TipoDocumentoOnibus
    descricao: str | None = None
    data_vencimento: date


class DocumentoOnibusUpdate(BaseModel):
    descricao: str | None = None
    data_vencimento: date | None = None


class DocumentoOnibusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    onibus_id: int
    tipo: TipoDocumentoOnibus
    descricao: str | None
    data_vencimento: date
    criado_em: datetime


class PoltronaLayout(BaseModel):
    numero: str
    andar: int = 1
    fileira: int
    coluna: int
    categoria: str = "padrao"
    multiplicador_preco: float = 1.00


class OnibusCreate(BaseModel):
    identificacao: str
    tipo: TipoOnibus
    poltronas: list[PoltronaLayout] = Field(default_factory=list)
    total_poltronas: int | None = Field(
        default=None,
        description="Se `poltronas` não for informado, gera automaticamente um layout 2+2 com esse total.",
    )


class PoltronaOnibusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero: str
    andar: int
    fileira: int
    coluna: int
    categoria: str
    multiplicador_preco: float


class PoltronaOnibusUpdate(BaseModel):
    categoria: str
    multiplicador_preco: float = Field(gt=0, le=10)


class OnibusUpdate(BaseModel):
    identificacao: str | None = None
    tipo: TipoOnibus | None = None
    quilometragem_atual: float | None = None


class OnibusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    identificacao: str
    tipo: TipoOnibus
    ativo: bool
    quilometragem_atual: float | None = None
    poltronas: list[PoltronaOnibusOut] = Field(default_factory=list)
    documentos: list[DocumentoOnibusOut] = Field(default_factory=list)
