from app.config import settings
from app.models.empresa import Empresa
from app.services.pagamento_provider import (
    MercadoPagoProvider,
    PagamentoSimuladoProvider,
    modo_simulado,
    obter_provider,
)
from tests.helpers import auth_header, criar_empresa_completa, login


def test_sem_nenhuma_chave_usa_provider_simulado(monkeypatch):
    monkeypatch.setattr(settings, "gateway_api_key", None)
    assert isinstance(obter_provider(), PagamentoSimuladoProvider)
    assert modo_simulado() is True


def test_empresa_com_token_proprio_usa_mercadopago_mesmo_sem_chave_global(monkeypatch):
    monkeypatch.setattr(settings, "gateway_api_key", None)
    empresa = Empresa(nome="Viação X", cnpj="00.000.000/0001-00", mercadopago_access_token="TOKEN-DA-EMPRESA")

    provider = obter_provider(empresa)
    assert isinstance(provider, MercadoPagoProvider)
    assert provider.api_key == "TOKEN-DA-EMPRESA"
    assert modo_simulado(empresa) is False


def test_empresa_sem_token_proprio_cai_para_chave_global(monkeypatch):
    monkeypatch.setattr(settings, "gateway_api_key", "TOKEN-GLOBAL")
    empresa = Empresa(nome="Viação Y", cnpj="00.000.000/0002-00")

    provider = obter_provider(empresa)
    assert isinstance(provider, MercadoPagoProvider)
    assert provider.api_key == "TOKEN-GLOBAL"


def test_chamada_sem_empresa_nunca_usa_token_de_tenant(monkeypatch):
    """Faturas (assinatura da empresa no GoTur) sempre usam só a chave
    global da plataforma — nunca a do tenant, senão a empresa pagaria a
    própria assinatura com o dinheiro que ela mesma recebe dos clientes."""
    monkeypatch.setattr(settings, "gateway_api_key", None)
    assert isinstance(obter_provider(), PagamentoSimuladoProvider)


def test_configurar_e_remover_credenciais_mercadopago(client, db):
    empresa = criar_empresa_completa(db, "MP1")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    inicial = client.get("/api/empresas/minha", headers=headers).json()
    assert inicial["mercadopago_configurado"] is False
    assert "mercadopago_access_token" not in inicial

    configurado = client.patch(
        "/api/empresas/minha/pagamento",
        json={"mercadopago_access_token": "APP_USR-teste-123", "mercadopago_public_key": "chave-publica"},
        headers=headers,
    )
    assert configurado.status_code == 200, configurado.text
    corpo = configurado.json()
    assert corpo["mercadopago_configurado"] is True
    assert corpo["mercadopago_public_key"] == "chave-publica"
    assert "mercadopago_access_token" not in corpo

    removido = client.patch(
        "/api/empresas/minha/pagamento",
        json={"mercadopago_access_token": "", "mercadopago_public_key": ""},
        headers=headers,
    )
    assert removido.status_code == 200
    assert removido.json()["mercadopago_configurado"] is False


def test_funcionario_nao_configura_pagamento(client, db):
    empresa = criar_empresa_completa(db, "MP2")
    headers = auth_header(login(client, empresa["funcionario_email"], empresa["senha"]))

    resposta = client.patch("/api/empresas/minha/pagamento", json={"mercadopago_access_token": "x"}, headers=headers)
    assert resposta.status_code == 403
