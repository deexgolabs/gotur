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
    viagem_id: int | None = None
    cliente_nome: str | None = None
    cliente_documento: str | None = None
    poltrona_numero: str | None = None
    origem_trecho: str | None = None
    destino_trecho: str | None = None
    # True quando não há gateway real configurado pra essa empresa (ou o
    # modo de cobrança é MANUAL) — controla se a tela mostra o botão de
    # "confirmar manualmente" ou só espera a confirmação automática.
    pagamento_simulado: bool = True


class CompraPassagemResponse(BaseModel):
    passagem: PassagemOut | None = None
    pedido_pagamento: PedidoPagamentoOut | None = None
