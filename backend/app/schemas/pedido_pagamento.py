from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import FormaPagamento, StatusPedidoPagamento
from app.schemas.passagem import PassagemOut


class PedidoPagamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: StatusPedidoPagamento
    valor: float
    forma_pagamento: FormaPagamento
    pix_copia_cola: str
    expira_em: datetime
    criado_em: datetime
    passagem_id: int | None = None


class CompraPassagemResponse(BaseModel):
    passagem: PassagemOut | None = None
    pedido_pagamento: PedidoPagamentoOut | None = None
