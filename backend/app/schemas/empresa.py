from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ModoCobranca, StatusAssinatura
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


class ConfiguracaoEmpresaRequest(BaseModel):
    nome: str | None = None
    email_contato: str | None = None
    telefone_contato: str | None = None
    texto_loja: str | None = None


class ConfiguracaoMarcaRequest(BaseModel):
    slug: str | None = None
    cor_primaria: str | None = None


class ConfiguracaoModulosRequest(BaseModel):
    fretamento_ativo: bool | None = None
    passagens_ativo: bool | None = None
    frete_ativo: bool | None = None


class ConfiguracaoFidelidadeRequest(BaseModel):
    fidelidade_ativa: bool | None = None
    fidelidade_passagens_necessarias: int | None = None
    fidelidade_desconto_percentual: float | None = None


class ConfiguracaoPagamentoRequest(BaseModel):
    """Credenciais do Mercado Pago da PRÓPRIA empresa + modo de cobrança.
    Envie apenas os campos que quer alterar (deixe de fora pra manter o
    que já está salvo); envie string vazia pra apagar um campo já salvo."""

    mercadopago_access_token: str | None = None
    mercadopago_public_key: str | None = None
    modo_cobranca: ModoCobranca | None = None


class TrocarPlanoRequest(BaseModel):
    plano_id: int


class EmpresaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    cnpj: str
    email_contato: str | None
    telefone_contato: str | None = None
    texto_loja: str | None = None
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
    fidelidade_ativa: bool = False
    fidelidade_passagens_necessarias: int | None = None
    fidelidade_desconto_percentual: float | None = None
    mercadopago_public_key: str | None = None
    mercadopago_configurado: bool = False
    modo_cobranca: ModoCobranca = ModoCobranca.AUTOMATICA


class LojaInfoOut(BaseModel):
    id: int
    nome: str
    slug: str
    cor_primaria: str
    logo_url: str | None = None
    telefone_contato: str | None = None
    texto_loja: str | None = None
    fretamento_habilitado: bool = True
    passagens_habilitado: bool = True
    frete_habilitado: bool = True
