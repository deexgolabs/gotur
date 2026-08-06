from pydantic import BaseModel


class EmpresaPertoDoLimiteOut(BaseModel):
    empresa_id: int
    empresa_nome: str
    recurso: str
    atual: int
    limite: int


class MetricasPlataformaOut(BaseModel):
    total_empresas: int
    empresas_ativas: int
    empresas_trial: int
    empresas_inadimplentes: int
    empresas_suspensas: int
    mrr: float
    empresas_perto_do_limite: list[EmpresaPertoDoLimiteOut]
