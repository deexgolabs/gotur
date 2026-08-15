from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import FormaPagamento, StatusPassagem, StatusPedidoPagamento


class ComprarIngressoRequest(BaseModel):
    assento_sessao_id: int
    cliente_nome: str
    cliente_documento: str
    forma_pagamento: FormaPagamento

    # Só usados quando forma_pagamento == "cartao" (Card Payment Brick,
    # ver frontend/js/mercadopago-checkout.js).
    mp_token: str | None = None
    mp_payment_method_id: str | None = None
    mp_installments: int | None = None
    mp_payer_email: str | None = None


class IngressoOut(BaseModel):
    id: int
    sessao_id: int
    assento_sessao_id: int
    cliente_nome: str
    cliente_documento: str
    preco: float
    forma_pagamento: FormaPagamento
    status: StatusPassagem
    codigo: str
    criado_em: datetime
    checkin_em: datetime | None = None
    valor_reembolsado: float | None = None
    motivo_reembolso: str | None = None
    reembolsado_em: datetime | None = None
    nome_evento: str | None = None
    local_nome: str | None = None
    data_hora: datetime | None = None
    numero_assento: str | None = None
    empresa_nome: str | None = None


class PedidoIngressoOut(BaseModel):
    id: int
    sessao_id: int
    status: StatusPedidoPagamento
    valor: float
    forma_pagamento: FormaPagamento
    pix_copia_cola: str | None = None
    expira_em: datetime
    criado_em: datetime
    ingresso_id: int | None = None
    # True quando não há gateway real configurado — mesmo controle usado
    # em PedidoPagamentoOut/PedidoInterlineOut/FaturaOut.
    pagamento_simulado: bool = True


class CompraIngressoResponse(BaseModel):
    ingresso: IngressoOut | None = None
    pedido_ingresso: PedidoIngressoOut | None = None


class ReembolsarIngressoRequest(BaseModel):
    valor: float | None = None
    motivo: str


class ReembolsoIngressoOut(BaseModel):
    ingresso_id: int
    valor_pago: float
    valor_reembolsado: float
    motivo_reembolso: str
    reembolsado_em: datetime
