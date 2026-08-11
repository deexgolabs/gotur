from pydantic import BaseModel


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
