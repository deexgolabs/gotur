from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import FormaPagamento, StatusFatura, StatusMatricula, TipoMatricula


class MatriculaCreate(BaseModel):
    """Usado só pelo staff (`POST /matriculas`) — o preço é negociado caso
    a caso. O autoatendimento pela loja usa `MatriculaLojaCreate`, sem
    campo de preço: o cliente nunca escolhe a própria mensalidade."""

    cliente_usuario_id: int
    tipo: TipoMatricula
    valor_mensalidade: float
    aulas_por_ciclo: int | None = None


class MatriculaLojaCreate(BaseModel):
    tipo: TipoMatricula
    aulas_por_ciclo: int | None = None


class MatriculaOut(BaseModel):
    id: int
    cliente_usuario_id: int
    cliente_nome: str | None = None
    tipo: TipoMatricula
    valor_mensalidade: float
    aulas_por_ciclo: int | None = None
    aulas_utilizadas_ciclo_atual: int
    status: StatusMatricula
    criado_em: datetime
    cancelada_em: datetime | None = None


class FaturaMatriculaOut(BaseModel):
    id: int
    matricula_id: int
    valor: float
    status: StatusFatura
    vencimento: date
    pago_em: datetime | None = None
    forma_pagamento: FormaPagamento | None = None
    pix_copia_cola: str | None = None
    pix_expira_em: datetime | None = None
    criado_em: datetime
    # True quando não há gateway real configurado — mesmo controle usado
    # em FaturaOut/PedidoIngressoOut.
    pagamento_simulado: bool = True


class PagarFaturaMatriculaRequest(BaseModel):
    forma_pagamento: FormaPagamento = FormaPagamento.PIX

    # Só usados quando forma_pagamento == "cartao" (Card Payment Brick,
    # ver frontend/js/mercadopago-checkout.js).
    mp_token: str | None = None
    mp_payment_method_id: str | None = None
    mp_installments: int | None = None
    mp_payer_email: str | None = None
