"""Abstração do provedor de pagamento.

Sem nenhuma chave configurada, roda em modo simulado
(`PagamentoSimuladoProvider`): Pix gera um código copia-e-cola de mentira e
fica pendente até alguém confirmar (tela "já paguei" no v1, ou o webhook de
um gateway real no futuro); cartão, dinheiro e outros meios aprovam na hora.
Isso deixa o restante do sistema (fluxo de compra, faturas, frontend) já
pronto para um gateway real — só falta configurar uma chave de verdade.

Duas configurações diferentes, dois donos diferentes do dinheiro:
- `ConfiguracaoPlataforma` (linha única, editada pelo super admin em
  Plataforma > Cobrança das empresas — com `GOTUR_GATEWAY_API_KEY` no
  `.env` como fallback se o super admin não configurar nada pela tela):
  usada pra cobrar a assinatura da EMPRESA no Vion
  (`app/routers/faturas.py`) — o dinheiro vai pra conta do dono da
  plataforma. `obter_provider(plataforma=...)`/`modo_simulado(plataforma=...)`
  usam essa configuração.
- `Empresa.mercadopago_access_token` (por tenant, configurado em
  Configurações > Pagamento): usada pra cobrar o CLIENTE da empresa
  (passagem, frete, fretamento) — o dinheiro vai pra conta da própria
  empresa, não pra do Vion. `obter_provider(empresa=...)`/`modo_simulado(empresa=...)`
  usam essa chave quando presente, caindo pra `GOTUR_GATEWAY_API_KEY` como
  fallback só se a empresa ainda não configurou a própria.

Nunca passe `empresa` e `plataforma` ao mesmo tempo — são contextos de
cobrança diferentes. Chamado sem nenhum dos dois, usa só a chave global
(`GOTUR_GATEWAY_API_KEY`), sem nenhum modo de cobrança customizado.
"""

import json
import logging
import secrets
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models.configuracao_plataforma import ConfiguracaoPlataforma
from app.models.empresa import Empresa
from app.models.enums import FormaPagamento, ModoCobranca

logger = logging.getLogger("gotur.pagamento")


@dataclass
class ResultadoCobranca:
    gateway_ref: str | None
    status: str  # "pendente" | "aprovado" | "recusado"
    pix_copia_cola: str | None = None
    pix_expira_em: datetime | None = None


@dataclass
class DadosCartao:
    """Vem do Card Payment Brick do Mercado Pago rodando no navegador do
    cliente — o número do cartão nunca passa pelo nosso backend, só esse
    token já tokenizado (ver frontend/js/mercadopago-checkout.js)."""

    token: str
    payment_method_id: str
    installments: int = 1
    payer_email: str | None = None
    payer_documento: str | None = None  # CPF/CNPJ — a maioria dos emissores brasileiros exige


class PagamentoProvider(ABC):
    @abstractmethod
    def cobrar(
        self,
        *,
        forma_pagamento: FormaPagamento,
        valor: float,
        referencia_pedido: str,
        dados_cartao: DadosCartao | None = None,
    ) -> ResultadoCobranca:
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

    def cobrar(
        self, *, forma_pagamento: FormaPagamento, valor: float, referencia_pedido: str, dados_cartao: DadosCartao | None = None
    ) -> ResultadoCobranca:
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
    dinheiro) e só quer usar o Vion pra controlar poltrona/vaga."""

    def cobrar(
        self, *, forma_pagamento: FormaPagamento, valor: float, referencia_pedido: str, dados_cartao: DadosCartao | None = None
    ) -> ResultadoCobranca:
        return ResultadoCobranca(gateway_ref=None, status="aprovado")


class PagamentoPendenteManualProvider(PagamentoProvider):
    """`Empresa.modo_cobranca = MANUAL`: toda venda fica pendente até um
    funcionário confirmar o pagamento na tela — mesmo cartão e dinheiro,
    que nos outros modos aprovam na hora. Pra empresa que prefere cobrar
    por fora mas ainda quer controlar manualmente quando a passagem é
    liberada (em vez de aprovar tudo sozinho, como em DESATIVADA)."""

    def cobrar(
        self, *, forma_pagamento: FormaPagamento, valor: float, referencia_pedido: str, dados_cartao: DadosCartao | None = None
    ) -> ResultadoCobranca:
        return ResultadoCobranca(
            gateway_ref=None,
            status="pendente",
            pix_copia_cola=_gerar_pix_copia_cola_simulado(valor, referencia_pedido),
            pix_expira_em=datetime.now(timezone.utc) + timedelta(minutes=settings.pix_expiracao_minutos),
        )


def _somente_digitos(texto: str) -> str:
    return "".join(c for c in texto if c.isdigit())


class MercadoPagoProvider(PagamentoProvider):
    """Integração real com o Mercado Pago via API REST (Access Token em
    `GOTUR_GATEWAY_API_KEY`, ou por empresa/plataforma — pegue o de
    produção em https://www.mercadopago.com.br/developers/panel/app).

    Pix: cria a cobrança e devolve o código copia-e-cola real. A
    `notification_url` enviada ao Mercado Pago faz ele chamar de volta
    `POST {GOTUR_BASE_URL}/api/webhooks/mercadopago` assim que o Pix cai —
    é o que confirma o pagamento de verdade (ver app/routers/webhooks.py).
    O endpoint `/pedidos-pagamento/{id}/confirmar-simulado` fica
    desabilitado automaticamente quando o gateway real está configurado
    (ver `modo_simulado()`), porque não faz sentido "confirmar
    manualmente" um Pix de verdade — quem confirma é o webhook.

    Cartão: usa o token gerado pelo Card Payment Brick no navegador do
    cliente (`frontend/js/mercadopago-checkout.js`) — o número do cartão
    nunca passa pelo nosso backend. Cartão aprova/recusa na hora (síncrono),
    diferente do Pix que fica pendente até o webhook confirmar.

    Dinheiro/outro: não passam pelo gateway — aprovados na hora aqui
    mesmo, sem gerar nenhuma cobrança no Mercado Pago (faz sentido: é uma
    venda paga por fora, não tem o que cobrar online).
    """

    API_BASE = "https://api.mercadopago.com"

    def __init__(self, api_key: str, taxa_aplicacao_percentual: float | None = None):
        self.api_key = api_key
        # Split de marketplace (ver ConfiguracaoPlataforma.taxa_transacao_percentual)
        # — só tem efeito de verdade se a conta da empresa estiver
        # conectada como sub-conta via OAuth marketplace do Mercado Pago;
        # com um Access Token colado manualmente (o modelo usado hoje), o
        # Mercado Pago tende a ignorar ou recusar o `application_fee`.
        self.taxa_aplicacao_percentual = taxa_aplicacao_percentual

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

    def _application_fee(self, valor: float) -> float | None:
        if not self.taxa_aplicacao_percentual:
            return None
        return round(float(valor) * self.taxa_aplicacao_percentual / 100, 2)

    def _notification_url(self) -> str:
        return f"{settings.base_url.rstrip('/')}/api/webhooks/mercadopago"

    def cobrar(
        self,
        *,
        forma_pagamento: FormaPagamento,
        valor: float,
        referencia_pedido: str,
        dados_cartao: DadosCartao | None = None,
    ) -> ResultadoCobranca:
        if forma_pagamento == FormaPagamento.PIX:
            return self._cobrar_pix(valor, referencia_pedido)
        if forma_pagamento == FormaPagamento.CARTAO:
            return self._cobrar_cartao(valor, referencia_pedido, dados_cartao)
        # Dinheiro/outro: pago por fora, nada a cobrar no gateway.
        return ResultadoCobranca(gateway_ref=None, status="aprovado")

    def _cobrar_pix(self, valor: float, referencia_pedido: str) -> ResultadoCobranca:
        corpo = {
            "transaction_amount": round(float(valor), 2),
            "description": f"Vion - {referencia_pedido}",
            "payment_method_id": "pix",
            "payer": {"email": f"comprador+{referencia_pedido}@gotur.app"},
            "notification_url": self._notification_url(),
        }
        taxa = self._application_fee(valor)
        if taxa:
            corpo["application_fee"] = taxa

        resultado = self._chamar("POST", "/v1/payments", corpo)

        dados_pix = resultado.get("point_of_interaction", {}).get("transaction_data", {})
        expira_em = resultado.get("date_of_expiration")

        return ResultadoCobranca(
            gateway_ref=str(resultado["id"]),
            status="pendente" if resultado.get("status") == "pending" else "aprovado",
            pix_copia_cola=dados_pix.get("qr_code"),
            pix_expira_em=datetime.fromisoformat(expira_em) if expira_em else datetime.now(timezone.utc) + timedelta(minutes=settings.pix_expiracao_minutos),
        )

    def _cobrar_cartao(self, valor: float, referencia_pedido: str, dados_cartao: DadosCartao | None) -> ResultadoCobranca:
        if not dados_cartao or not dados_cartao.token:
            raise ValueError(
                "Pagamento por cartão exige o token gerado pelo Card Payment Brick no navegador do "
                "cliente (ver frontend/js/mercadopago-checkout.js) — nenhum token foi enviado."
            )

        payer: dict = {"email": dados_cartao.payer_email or f"comprador+{referencia_pedido}@gotur.app"}
        if dados_cartao.payer_documento:
            digitos = _somente_digitos(dados_cartao.payer_documento)
            payer["identification"] = {"type": "CPF" if len(digitos) <= 11 else "CNPJ", "number": digitos}

        corpo = {
            "transaction_amount": round(float(valor), 2),
            "description": f"Vion - {referencia_pedido}",
            "token": dados_cartao.token,
            "installments": dados_cartao.installments or 1,
            "payment_method_id": dados_cartao.payment_method_id,
            "payer": payer,
            "notification_url": self._notification_url(),
        }
        taxa = self._application_fee(valor)
        if taxa:
            corpo["application_fee"] = taxa

        resultado = self._chamar("POST", "/v1/payments", corpo)
        status_mp = resultado.get("status")
        if status_mp == "approved":
            status_local = "aprovado"
        elif status_mp in ("rejected", "cancelled"):
            status_local = "recusado"
        else:
            status_local = "pendente"

        return ResultadoCobranca(gateway_ref=str(resultado["id"]), status=status_local)

    def consultar_status(self, gateway_ref: str) -> str:
        """`status` bruto do Mercado Pago: "pending", "approved", "rejected"
        etc. Usado pelo webhook (`app/routers/webhooks.py`) pra revalidar
        server-a-server o que o Mercado Pago notificou, em vez de confiar
        cegamente no corpo do webhook (que qualquer um poderia forjar)."""
        resultado = self._chamar("GET", f"/v1/payments/{gateway_ref}")
        return resultado.get("status", "pending")


def obter_configuracao_plataforma(db: Session) -> ConfiguracaoPlataforma:
    """`ConfiguracaoPlataforma` é uma linha única (singleton) — cria na
    primeira vez que alguém precisar dela (não existe tela de "criar",
    só de editar)."""
    config = db.query(ConfiguracaoPlataforma).first()
    if not config:
        config = ConfiguracaoPlataforma()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def _chave_ativa(empresa: Empresa | None, plataforma: ConfiguracaoPlataforma | None) -> str | None:
    if empresa is not None and empresa.mercadopago_access_token:
        return empresa.mercadopago_access_token
    if plataforma is not None and plataforma.mercadopago_access_token:
        return plataforma.mercadopago_access_token
    return settings.gateway_api_key


def _modo_cobranca_ativo(empresa: Empresa | None, plataforma: ConfiguracaoPlataforma | None) -> ModoCobranca:
    if empresa is not None:
        return empresa.modo_cobranca
    if plataforma is not None:
        return plataforma.modo_cobranca
    return ModoCobranca.AUTOMATICA


def obter_provider(
    empresa: Empresa | None = None,
    plataforma: ConfiguracaoPlataforma | None = None,
    taxa_transacao_percentual: float | None = None,
) -> PagamentoProvider:
    """Sem `empresa` nem `plataforma`, usa só a chave global, sem nenhum
    modo de cobrança customizado. Com um dos dois, o modo de cobrança
    escolhido manda: MANUAL e DESATIVADA ignoram completamente se tem
    Mercado Pago configurado ou não; só AUTOMATICA de fato olha pra chave
    (própria, ou a global como fallback). Nunca passe os dois juntos.

    `taxa_transacao_percentual` (ver ConfiguracaoPlataforma) só faz
    sentido pra cobrança de EMPRESA (venda pro cliente dela) — nunca pra
    cobrança da própria fatura da plataforma, por isso é ignorado quando
    `plataforma` é passado em vez de `empresa`."""
    modo = _modo_cobranca_ativo(empresa, plataforma)
    if modo == ModoCobranca.DESATIVADA:
        return PagamentoManualProvider()
    if modo == ModoCobranca.MANUAL:
        return PagamentoPendenteManualProvider()

    chave = _chave_ativa(empresa, plataforma)
    if chave:
        taxa = taxa_transacao_percentual if empresa is not None else None
        return MercadoPagoProvider(chave, taxa_aplicacao_percentual=taxa)
    return PagamentoSimuladoProvider()


def modo_simulado(empresa: Empresa | None = None, plataforma: ConfiguracaoPlataforma | None = None) -> bool:
    """Controla se a confirmação manual (`/pedidos-pagamento/{id}/confirmar-simulado`,
    `/faturas/{id}/confirmar-simulado`) fica disponível. Em MANUAL, sempre
    disponível (é assim que a venda/fatura é liberada). Em DESATIVADA,
    nunca fica pendente pra começo de conversa, então não há o que
    confirmar."""
    modo = _modo_cobranca_ativo(empresa, plataforma)
    if modo == ModoCobranca.MANUAL:
        return True
    if modo == ModoCobranca.DESATIVADA:
        return False
    return not _chave_ativa(empresa, plataforma)
