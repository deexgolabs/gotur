from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ParceiroCreate(BaseModel):
    nome: str
    documento: str | None = None
    contato: str | None = None
    vende_passagem: bool = True
    despacha_frete: bool = True
    comissao_percentual: float | None = Field(default=None, ge=0, le=100)


class ParceiroUpdate(BaseModel):
    nome: str | None = None
    documento: str | None = None
    contato: str | None = None
    vende_passagem: bool | None = None
    despacha_frete: bool | None = None
    comissao_percentual: float | None = Field(default=None, ge=0, le=100)
    ativo: bool | None = None


class ParceiroOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    documento: str | None
    contato: str | None
    vende_passagem: bool
    despacha_frete: bool
    comissao_percentual: float | None
    ativo: bool
    criado_em: datetime
    tem_acesso: bool = False


class CriarAcessoParceiroRequest(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=6)


class ResumoParceiroOut(BaseModel):
    parceiro_nome: str
    comissao_percentual: float | None
    total_passagens: int
    total_arrecadado_passagens: float
    total_fretes: int
    total_arrecadado_fretes: float
    comissao_estimada: float
