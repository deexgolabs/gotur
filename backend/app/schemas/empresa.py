from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import StatusAssinatura
from app.schemas.plano import PlanoOut




class EmpresaCreate(BaseModel):
    nome: str
    cnpj: str
    email_contato: str | None = None
    plano_id: int | None = None


class EmpresaUpdate(BaseModel):
    nome: str | None = None
    email_contato: str | None = None


class ConfiguracaoFretamentoRequest(BaseModel):
    preco_km_fretamento: float | None = None


class ConfiguracaoMarcaRequest(BaseModel):
    slug: str | None = None
    cor_primaria: str | None = None


class ConfiguracaoModulosRequest(BaseModel):
    fretamento_ativo: bool | None = None
    passagens_ativo: bool | None = None
    frete_ativo: bool | None = None


class TrocarPlanoRequest(BaseModel):
    plano_id: int


class EmpresaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    cnpj: str
    email_contato: str | None
    ativo: bool
    criado_em: datetime
    plano_id: int | None
    status_assinatura: StatusAssinatura
    plano: PlanoOut | None = None
    preco_km_fretamento: float | None = None
    slug: str | None = None
    cor_primaria: str | None = None
    logo_url: str | None = None
    fretamento_ativo: bool = True
    passagens_ativo: bool = True
    frete_ativo: bool = True
    fretamento_habilitado: bool = True
    passagens_habilitado: bool = True
    frete_habilitado: bool = True


class LojaInfoOut(BaseModel):
    id: int
    nome: str
    slug: str
    cor_primaria: str
    logo_url: str | None = None
    fretamento_habilitado: bool = True
    passagens_habilitado: bool = True
    frete_habilitado: bool = True
