import pytest

from app.config import settings
from app.models.enums import FormaPagamento
from app.services.pagamento_provider import (
    MercadoPagoProvider,
    PagamentoSimuladoProvider,
    modo_simulado,
    obter_provider,
)


def test_sem_chave_configurada_usa_provider_simulado():
    assert settings.gateway_api_key is None
    assert modo_simulado() is True
    assert isinstance(obter_provider(), PagamentoSimuladoProvider)


def test_com_chave_configurada_usa_mercado_pago(monkeypatch):
    monkeypatch.setattr(settings, "gateway_api_key", "TEST-CHAVE-FAKE")
    assert modo_simulado() is False
    assert isinstance(obter_provider(), MercadoPagoProvider)


def test_mercado_pago_cartao_ainda_nao_implementado():
    provider = MercadoPagoProvider(api_key="TEST-CHAVE-FAKE")
    with pytest.raises(NotImplementedError):
        provider.cobrar(forma_pagamento=FormaPagamento.CARTAO, valor=100.0, referencia_pedido="ref-1")
