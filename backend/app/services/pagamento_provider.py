"""Abstração do provedor de pagamento.

Sem `GOTUR_GATEWAY_API_KEY` configurado, roda em modo simulado
(`PagamentoSimuladoProvider`): Pix gera um código copia-e-cola de mentira e
fica pendente até alguém confirmar (tela "já paguei" no v1, ou o webhook de
um gateway real no futuro); cartão, dinheiro e outros meios aprovam na hora.
Isso deixa o restante do sistema (fluxo de compra, faturas, frontend) já
pronto para um gateway real — só falta implementar `cobrar()` de verdade.

Para plugar um gateway real (Mercado Pago, Stripe, Asaas etc.) no futuro:
1. Implemente `cobrar()` em uma nova classe que herde de `PagamentoProvider`
   (veja o esqueleto em `MercadoPagoProvider`).
2. Configure a variável de ambiente `GOTUR_GATEWAY_API_KEY`.
3. Nenhum outro ponto do sistema precisa mudar — `obter_provider()` já troca
   automaticamente o provider usado nos routers de passagens e faturas.
"""

import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.models.enums import FormaPagamento


@dataclass
class ResultadoCobranca:
    gateway_ref: str | None
    status: str  # "pendente" | "aprovado" | "recusado"
    pix_copia_cola: str | None = None
    pix_expira_em: datetime | None = None


class PagamentoProvider(ABC):
    @abstractmethod
    def cobrar(self, *, forma_pagamento: FormaPagamento, valor: float, referencia_pedido: str) -> ResultadoCobranca:
        ...


def _gerar_pix_copia_cola_simulado(valor: float, referencia_pedido: str) -> str:
    """Código no formato visual de um Pix (BR Code / EMV), mas de mentira —
    não é aceito por nenhum banco. Serve só para a tela de pagamento
    simulado mostrar algo com a cara de um Pix de verdade."""
    identificador = secrets.token_hex(8).upper()
    valor_formatado = f"{valor:.2f}"
    return f"00020126SIMULADO-GOTUR{referencia_pedido}5204000053039865{len(valor_formatado)}{valor_formatado}5802BR6009GOTUR SIM62070503{identificador}6304SIMU"


class PagamentoSimuladoProvider(PagamentoProvider):
    """Provider padrão (v2) quando nenhum gateway real está configurado."""

    def cobrar(self, *, forma_pagamento: FormaPagamento, valor: float, referencia_pedido: str) -> ResultadoCobranca:
        if forma_pagamento == FormaPagamento.PIX:
            return ResultadoCobranca(
                gateway_ref=None,
                status="pendente",
                pix_copia_cola=_gerar_pix_copia_cola_simulado(valor, referencia_pedido),
                pix_expira_em=datetime.now(timezone.utc) + timedelta(minutes=settings.pix_expiracao_minutos),
            )
        return ResultadoCobranca(gateway_ref=None, status="aprovado")


class PagamentoManualProvider(PagamentoProvider):
    """Comportamento antigo (v1): registra qualquer forma de pagamento como
    aprovada na hora, sem gerar Pix pendente. Mantido só por compatibilidade
    — não é mais usado por padrão, ver `obter_provider()`."""

    def cobrar(self, *, forma_pagamento: FormaPagamento, valor: float, referencia_pedido: str) -> ResultadoCobranca:
        return ResultadoCobranca(gateway_ref=None, status="aprovado")


class MercadoPagoProvider(PagamentoProvider):
    """Esqueleto pronto para a integração real com o Mercado Pago.

    Ainda não implementado: chamar a API do Mercado Pago para criar a
    cobrança e devolver o `payment_id` como `gateway_ref` (e o código Pix
    real em `pix_copia_cola` quando a forma de pagamento for Pix).
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
    return PagamentoSimuladoProvider()


def modo_simulado() -> bool:
    return not settings.gateway_api_key
