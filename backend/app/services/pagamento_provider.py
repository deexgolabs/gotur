"""Abstração do provedor de pagamento.

V1 usa apenas o registro manual (`PagamentoManualProvider`): o funcionário ou
cliente informa a forma de pagamento e o sistema registra, sem cobrança real.

Para plugar um gateway real (Mercado Pago, Stripe, etc.) no futuro:
1. Implemente `cobrar()` em uma nova classe que herde de `PagamentoProvider`
   (veja o esqueleto em `MercadoPagoProvider`).
2. Configure a variável de ambiente `GOTUR_GATEWAY_API_KEY`.
3. Nenhum outro ponto do sistema precisa mudar — `obter_provider()` já troca
   automaticamente o provider usado em `routers/passagens.py`.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.config import settings
from app.models.enums import FormaPagamento


@dataclass
class ResultadoCobranca:
    gateway_ref: str | None
    status: str  # "registrado" | "pendente" | "aprovado" | "recusado"


class PagamentoProvider(ABC):
    @abstractmethod
    def cobrar(self, *, forma_pagamento: FormaPagamento, valor: float, referencia_pedido: str) -> ResultadoCobranca:
        ...


class PagamentoManualProvider(PagamentoProvider):
    """Comportamento atual (v1): apenas registra a forma de pagamento informada."""

    def cobrar(self, *, forma_pagamento: FormaPagamento, valor: float, referencia_pedido: str) -> ResultadoCobranca:
        return ResultadoCobranca(gateway_ref=None, status="registrado")


class MercadoPagoProvider(PagamentoProvider):
    """Esqueleto pronto para a integração real com o Mercado Pago.

    Ainda não implementado: chamar a API do Mercado Pago para criar a
    cobrança e devolver o `payment_id` como `gateway_ref`.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key

    def cobrar(self, *, forma_pagamento: FormaPagamento, valor: float, referencia_pedido: str) -> ResultadoCobranca:
        raise NotImplementedError(
            "Integração com gateway de pagamento ainda não implementada. "
            "Implemente MercadoPagoProvider.cobrar() antes de configurar GOTUR_GATEWAY_API_KEY."
        )


def obter_provider() -> PagamentoProvider:
    if settings.gateway_api_key:
        return MercadoPagoProvider(settings.gateway_api_key)
    return PagamentoManualProvider()
