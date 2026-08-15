from datetime import datetime

from pydantic import BaseModel

from app.models.enums import FormaPagamento, StatusPassagem, TipoReserva


class CriarReservaRequest(BaseModel):
    # Caminho matrícula: informe matricula_id (precisa estar ATIVA/INADIMPLENTE
    # e pertencer ao usuário logado, a menos que seja staff).
    matricula_id: int | None = None

    # Caminho avulso (drop-in): a Turma precisa ter preco_avulso definido.
    # Sem conta de cliente exige nome/documento livres, igual Ingresso.
    cliente_nome: str | None = None
    cliente_documento: str | None = None
    forma_pagamento: FormaPagamento | None = None

    # Só usados quando forma_pagamento == "cartao" (Card Payment Brick,
    # ver frontend/js/mercadopago-checkout.js).
    mp_token: str | None = None
    mp_payment_method_id: str | None = None
    mp_installments: int | None = None
    mp_payer_email: str | None = None


class ReservaAulaOut(BaseModel):
    id: int
    ocorrencia_turma_id: int
    nome_turma: str | None = None
    data_hora_inicio: datetime | None = None
    cliente_nome: str | None = None
    cliente_documento: str | None = None
    tipo_reserva: TipoReserva
    status: StatusPassagem
    preco_pago: float | None = None
    forma_pagamento: FormaPagamento | None = None
    codigo: str
    criado_em: datetime
    checkin_em: datetime | None = None
    cancelada_em: datetime | None = None
