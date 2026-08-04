from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TipoOnibus


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


class OnibusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    identificacao: str
    tipo: TipoOnibus
    ativo: bool
    poltronas: list[PoltronaOnibusOut] = Field(default_factory=list)
