import json
from unittest.mock import MagicMock, patch

import pytest

from app.config import settings
from app.models.enums import FormaPagamento
from app.services.pagamento_provider import DadosCartao, MercadoPagoProvider


def _mock_resposta(corpo: dict):
    mock = MagicMock()
    mock.__enter__.return_value.read.return_value = json.dumps(corpo).encode("utf-8")
    return mock


def test_cobrar_pix_inclui_notification_url(monkeypatch):
    monkeypatch.setattr(settings, "base_url", "https://minhaviacao.exemplo.com")
    provider = MercadoPagoProvider("TOKEN-TESTE")

    with patch("app.services.pagamento_provider.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _mock_resposta(
            {
                "id": 111,
                "status": "pending",
                "point_of_interaction": {"transaction_data": {"qr_code": "00020PIX"}},
            }
        )
        resultado = provider.cobrar(forma_pagamento=FormaPagamento.PIX, valor=50.0, referencia_pedido="ref-1")

        assert resultado.status == "pendente"
        assert resultado.pix_copia_cola == "00020PIX"
        requisicao = mock_urlopen.call_args[0][0]
        corpo_enviado = json.loads(requisicao.data)
        assert corpo_enviado["notification_url"] == "https://minhaviacao.exemplo.com/api/webhooks/mercadopago"
        assert "application_fee" not in corpo_enviado


def test_cobrar_cartao_aprovado(monkeypatch):
    provider = MercadoPagoProvider("TOKEN-TESTE")
    dados_cartao = DadosCartao(token="card-token-abc", payment_method_id="visa", installments=2, payer_documento="123.456.789-00")

    with patch("app.services.pagamento_provider.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _mock_resposta({"id": 222, "status": "approved"})
        resultado = provider.cobrar(
            forma_pagamento=FormaPagamento.CARTAO, valor=100.0, referencia_pedido="ref-2", dados_cartao=dados_cartao
        )

        assert resultado.status == "aprovado"
        assert resultado.gateway_ref == "222"
        requisicao = mock_urlopen.call_args[0][0]
        corpo_enviado = json.loads(requisicao.data)
        assert corpo_enviado["token"] == "card-token-abc"
        assert corpo_enviado["installments"] == 2
        assert corpo_enviado["payment_method_id"] == "visa"
        assert corpo_enviado["payer"]["identification"] == {"type": "CPF", "number": "12345678900"}


def test_cobrar_cartao_recusado(monkeypatch):
    provider = MercadoPagoProvider("TOKEN-TESTE")
    dados_cartao = DadosCartao(token="card-token-recusado", payment_method_id="master")

    with patch("app.services.pagamento_provider.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _mock_resposta({"id": 333, "status": "rejected"})
        resultado = provider.cobrar(
            forma_pagamento=FormaPagamento.CARTAO, valor=80.0, referencia_pedido="ref-3", dados_cartao=dados_cartao
        )
        assert resultado.status == "recusado"


def test_cobrar_cartao_sem_token_levanta_erro():
    provider = MercadoPagoProvider("TOKEN-TESTE")
    with pytest.raises(ValueError):
        provider.cobrar(forma_pagamento=FormaPagamento.CARTAO, valor=80.0, referencia_pedido="ref-4", dados_cartao=None)


def test_cobrar_dinheiro_nao_chama_gateway():
    provider = MercadoPagoProvider("TOKEN-TESTE")
    with patch("app.services.pagamento_provider.urllib.request.urlopen") as mock_urlopen:
        resultado = provider.cobrar(forma_pagamento=FormaPagamento.DINHEIRO, valor=30.0, referencia_pedido="ref-5")
        assert resultado.status == "aprovado"
        assert resultado.gateway_ref is None
        mock_urlopen.assert_not_called()


def test_application_fee_incluido_quando_taxa_configurada():
    provider = MercadoPagoProvider("TOKEN-TESTE", taxa_aplicacao_percentual=5.0)

    with patch("app.services.pagamento_provider.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _mock_resposta(
            {"id": 444, "status": "pending", "point_of_interaction": {"transaction_data": {"qr_code": "00020PIX"}}}
        )
        provider.cobrar(forma_pagamento=FormaPagamento.PIX, valor=200.0, referencia_pedido="ref-6")

        requisicao = mock_urlopen.call_args[0][0]
        corpo_enviado = json.loads(requisicao.data)
        assert corpo_enviado["application_fee"] == 10.0


def test_sem_taxa_configurada_nao_inclui_application_fee():
    provider = MercadoPagoProvider("TOKEN-TESTE")

    with patch("app.services.pagamento_provider.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _mock_resposta(
            {"id": 555, "status": "pending", "point_of_interaction": {"transaction_data": {"qr_code": "00020PIX"}}}
        )
        provider.cobrar(forma_pagamento=FormaPagamento.PIX, valor=200.0, referencia_pedido="ref-7")

        requisicao = mock_urlopen.call_args[0][0]
        corpo_enviado = json.loads(requisicao.data)
        assert "application_fee" not in corpo_enviado


def test_consultar_status():
    provider = MercadoPagoProvider("TOKEN-TESTE")
    with patch("app.services.pagamento_provider.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _mock_resposta({"id": 666, "status": "approved"})
        assert provider.consultar_status("666") == "approved"
