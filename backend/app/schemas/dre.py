from datetime import datetime

from pydantic import BaseModel


class DreOut(BaseModel):
    periodo_inicio: datetime
    periodo_fim: datetime

    receita_passagens: float
    receita_fretamento: float
    receita_frete: float
    receita_bruta_total: float

    reembolsos: float
    despesa_assinatura_gotur: float

    receita_liquida: float
