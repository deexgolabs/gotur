from pydantic import BaseModel, ConfigDict

from app.models.enums import ModoCobranca


class ConfiguracaoCobrancaPlataformaRequest(BaseModel):
    """Credenciais do Mercado Pago da PRÓPRIA plataforma GoTur + modo de
    cobrança das empresas clientes. Envie apenas os campos que quer
    alterar; envie string vazia pra apagar um campo já salvo."""

    mercadopago_access_token: str | None = None
    mercadopago_public_key: str | None = None
    modo_cobranca: ModoCobranca | None = None
    taxa_transacao_percentual: float | None = None


class ConfiguracaoCobrancaPlataformaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mercadopago_public_key: str | None = None
    mercadopago_configurado: bool = False
    modo_cobranca: ModoCobranca = ModoCobranca.AUTOMATICA
    taxa_transacao_percentual: float | None = None


class EmpresaPertoDoLimiteOut(BaseModel):
    empresa_id: int
    empresa_nome: str
    recurso: str
    atual: int
    limite: int


class MrrMesOut(BaseModel):
    mes: str  # "YYYY-MM"
    mrr: float


class EmpresaEmRiscoOut(BaseModel):
    empresa_id: int
    empresa_nome: str
    status_assinatura: str
    valor_em_atraso: float
    dias_em_atraso: int


class CrescimentoEmpresaOut(BaseModel):
    empresa_id: int
    empresa_nome: str
    passagens_mes_atual: int
    passagens_mes_anterior: int
    variacao_percentual: float | None  # None quando não dá pra calcular (mês anterior zerado)


class MetricasPlataformaOut(BaseModel):
    total_empresas: int
    empresas_ativas: int
    empresas_trial: int
    empresas_inadimplentes: int
    empresas_suspensas: int
    empresas_desativadas: int
    mrr: float
    mrr_historico: list[MrrMesOut]
    inadimplencia_total: float
    empresas_em_risco: list[EmpresaEmRiscoOut]
    top_crescimento: list[CrescimentoEmpresaOut]
    empresas_perto_do_limite: list[EmpresaPertoDoLimiteOut]
