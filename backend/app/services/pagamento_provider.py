"""Abstração do provedor de pagamento.

Sem nenhuma chave configurada, roda em modo simulado
(`PagamentoSimuladoProvider`): Pix gera um código copia-e-cola de mentira e
fica pendente até alguém confirmar (tela "já paguei" no v1, ou o webhook de
um gateway real no futuro); cartão, dinheiro e outros meios aprovam na hora.
Isso deixa o restante do sistema (fluxo de compra, faturas, frontend) já
pronto para um gateway real — só falta configurar uma chave de verdade.

Duas chaves diferentes, dois donos diferentes do dinheiro:
- `GOTUR_GATEWAY_API_KEY` (global, `.env` do servidor): usada só pra cobrar
  a assinatura da EMPRESA no GoTur (`app/routers/faturas.py`) — o dinheiro
  vai pra conta do dono da plataforma. `obter_provider()`/`modo_simulado()`
  chamados sem argumento usam só essa chave.
- `Empresa.mercadopago_access_token` (por tenant, configurado em
  Configurações > Pagamento): usada pra cobrar o CLIENTE da empresa
  (passagem, frete, fretamento) — o dinheiro vai pra conta da própria
  empresa, não pra do GoTur. `obter_provider(empresa)`/`modo_simulado(empresa)`
  usam essa chave quando presente, caindo pra `GOTUR_GATEWAY_API_KEY` como
  fallback só se a empresa ainda não configurou a própria.
"""

import json
import logging
import secrets
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.models.empresa import Empresa
from app.models.enums import FormaPagamento, ModoCobranca

logger = logging.getLogger("gotur.pagamento")


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
    """`Empresa.modo_cobranca = DESATIVADA`: registra qualquer forma de
    pagamento como aprovada na hora, sem gerar Pix pendente e sem checar
    nada — pra empresa que cobra 100% por fora (maquininha própria,
    dinheiro) e só quer usar o GoTur pra controlar poltrona/vaga."""

    def cobrar(self, *, forma_pagamento: FormaPagamento, valor: float, referencia_pedido: str) -> ResultadoCobranca:
        return ResultadoCobranca(gateway_ref=None, status="aprovado")


class PagamentoPendenteManualProvider(PagamentoProvider):
    """`Empresa.modo_cobranca = MANUAL`: toda venda fica pendente até um
    funcionário confirmar o pagamento na tela — mesmo cartão e dinheiro,
    que nos outros modos aprovam na hora. Pra empresa que prefere cobrar
    por fora mas ainda quer controlar manualmente quando a passagem é
    liberada (em vez de aprovar tudo sozinho, como em DESATIVADA)."""

    def cobrar(self, *, forma_pagamento: FormaPagamento, valor: float, referencia_pedido: str) -> ResultadoCobranca:
        return ResultadoCobranca(
            gateway_ref=None,
            status="pendente",
            pix_copia_cola=_gerar_pix_copia_cola_simulado(valor, referencia_pedido),
            pix_expira_em=datetime.now(timezone.utc) + timedelta(minutes=settings.pix_expiracao_minutos),
        )


class MercadoPagoProvider(PagamentoProvider):
    """Integração real com o Mercado Pago via API REST (Access Token em
    `GOTUR_GATEWAY_API_KEY` — pegue o de produção em
    https://www.mercadopago.com.br/developers/panel/app).

    Pix: implementado de verdade — cria a cobrança e devolve o código
    copia-e-cola real do Mercado Pago. A confirmação ainda depende de
    consultar o pagamento depois (`consultar_status`) ou de um webhook — o
    endpoint `/pedidos-pagamento/{id}/confirmar-simulado` fica desabilitado
    automaticamente quando o gateway real está configurado (ver
    `modo_simulado()`), porque não faz sentido "confirmar manualmente" um
    Pix de verdade.

    Cartão: ainda não implementado — o Mercado Pago exige tokenizar o
    cartão no navegador do cliente com o SDK deles (Card Payment Brick),
    então precisa de uma tela de checkout própria antes de plugar aqui.
    """

    API_BASE = "https://api.mercadopago.com"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _chamar(self, metodo: str, caminho: str, corpo: dict | None = None) -> dict:
        dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
        requisicao = urllib.request.Request(
            f"{self.API_BASE}{caminho}",
            data=dados,
            method=metodo,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Idempotency-Key": secrets.token_hex(16),
            },
        )
        try:
            with urllib.request.urlopen(requisicao, timeout=15) as resposta:
                return json.loads(resposta.read())
        except urllib.error.HTTPError as erro:
            corpo_erro = erro.read().decode("utf-8", errors="ignore")
            logger.error("Mercado Pago recusou a chamada %s %s: %s", metodo, caminho, corpo_erro)
            raise

    def cobrar(self, *, forma_pagamento: FormaPagamento, valor: float, referencia_pedido: str) -> ResultadoCobranca:
        if forma_pagamento != FormaPagamento.PIX:
            raise NotImplementedError(
                "Pagamento por cartão via Mercado Pago ainda não implementado — exige tokenizar o "
                "cartão no navegador do cliente (Card Payment Brick) antes de chamar a API. "
                "Pix já funciona de verdade com GOTUR_GATEWAY_API_KEY configurado."
            )

        resultado = self._chamar(
            "POST",
            "/v1/payments",
            {
                "transaction_amount": round(float(valor), 2),
                "description": f"GoTur - {referencia_pedido}",
                "payment_method_id": "pix",
                "payer": {"email": f"comprador+{referencia_pedido}@gotur.app"},
            },
        )

        dados_pix = resultado.get("point_of_interaction", {}).get("transaction_data", {})
        expira_em = resultado.get("date_of_expiration")

        return ResultadoCobranca(
            gateway_ref=str(resultado["id"]),
            status="pendente" if resultado.get("status") == "pending" else "aprovado",
            pix_copia_cola=dados_pix.get("qr_code"),
            pix_expira_em=datetime.fromisoformat(expira_em) if expira_em else datetime.now(timezone.utc) + timedelta(minutes=settings.pix_expiracao_minutos),
        )

    def consultar_status(self, gateway_ref: str) -> str:
        """`status` bruto do Mercado Pago: "pending", "approved", "rejected"
        etc. Use pra checar se um Pix criado por `cobrar()` já caiu, até um
        webhook de verdade ser implementado."""
        resultado = self._chamar("GET", f"/v1/payments/{gateway_ref}")
        return resultado.get("status", "pending")


def _chave_ativa(empresa: Empresa | None) -> str | None:
    if empresa is not None and empresa.mercadopago_access_token:
        return empresa.mercadopago_access_token
    return settings.gateway_api_key


def obter_provider(empresa: Empresa | None = None) -> PagamentoProvider:
    """Sem `empresa` (ex: cobrança da fatura da assinatura no GoTur), usa
    só a chave global — `Empresa.modo_cobranca` nunca entra em jogo. Com
    `empresa` (venda de passagem/frete/fretamento pro cliente dela), o modo
    de cobrança que ela escolheu em Configurações manda: MANUAL e
    DESATIVADA ignoram completamente se tem Mercado Pago configurado ou
    não; só AUTOMATICA de fato olha pra chave (própria da empresa, ou a
    global como fallback)."""
    if empresa is not None:
        if empresa.modo_cobranca == ModoCobranca.DESATIVADA:
            return PagamentoManualProvider()
        if empresa.modo_cobranca == ModoCobranca.MANUAL:
            return PagamentoPendenteManualProvider()

    chave = _chave_ativa(empresa)
    if chave:
        return MercadoPagoProvider(chave)
    return PagamentoSimuladoProvider()


def modo_simulado(empresa: Empresa | None = None) -> bool:
    """Controla se a confirmação manual (`/pedidos-pagamento/{id}/confirmar-simulado`)
    fica disponível. Em MANUAL, sempre disponível (é assim que a venda é
    liberada). Em DESATIVADA, nunca fica pendente pra começo de conversa,
    então não há o que confirmar."""
    if empresa is not None:
        if empresa.modo_cobranca == ModoCobranca.MANUAL:
            return True
        if empresa.modo_cobranca == ModoCobranca.DESATIVADA:
            return False
    return not _chave_ativa(empresa)
