from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import FormaPagamento, StatusFatura


class PagarFaturaRequest(BaseModel):
    forma_pagamento: FormaPagamento = FormaPagamento.PIX

    # Só usados quando forma_pagamento == "cartao" — vêm do Card Payment
    # Brick do Mercado Pago (ver frontend/js/mercadopago-checkout.js).
    mp_token: str | None = None
    mp_payment_method_id: str | None = None
    mp_installments: int | None = None
    mp_payer_email: str | None = None

    # Só usados quando forma_pagamento == "boleto" — o Mercado Pago exige
    # nome, CPF/CNPJ e endereço completo do pagador pra emitir boleto.
    boleto_nome: str | None = None
    boleto_cpf_cnpj: str | None = None
    boleto_cep: str | None = None
    boleto_logradouro: str | None = None
    boleto_numero: str | None = None
    boleto_bairro: str | None = None
    boleto_cidade: str | None = None
    boleto_uf: str | None = None


class FaturaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    empresa_id: int
    empresa_nome: str | None = None
    plano_id: int
    plano_nome: str | None = None
    valor: float
    status: StatusFatura
    vencimento: date
    pago_em: datetime | None
    criado_em: datetime
    forma_pagamento: FormaPagamento | None = None
    pix_copia_cola: str | None = None
    pix_expira_em: datetime | None = None
    boleto_url: str | None = None
    boleto_codigo_barras: str | None = None
    # True quando não há gateway real configurado (ou o modo de cobrança é
    # MANUAL) — controla se a tela mostra o botão de "confirmar manualmente"
    # ou se deve só esperar a confirmação automática (webhook do gateway).
    pagamento_simulado: bool = True
