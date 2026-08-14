from app.models.configuracao_plataforma import ConfiguracaoPlataforma
from app.models.enums import ModoCobranca
from app.services.pagamento_provider import (
    PagamentoManualProvider,
    PagamentoPendenteManualProvider,
    modo_simulado,
    obter_configuracao_plataforma,
    obter_provider,
)
from tests.helpers import auth_header, criar_empresa_completa, criar_super_admin, login


def _empresa_com_plano(client, db, sufixo: str):
    super_admin = criar_super_admin(db, sufixo)
    token_super = login(client, super_admin["email"], super_admin["senha"])
    headers_super = auth_header(token_super)
    plano = client.post(
        "/api/planos",
        json={"nome": "Basico", "preco_mensal": 99.9, "max_onibus": 1, "max_funcionarios": 2, "max_viagens_mes": 1},
        headers=headers_super,
    ).json()

    empresa = criar_empresa_completa(db, sufixo)
    from app.models.empresa import Empresa

    db_empresa = db.get(Empresa, empresa["empresa_id"])
    db_empresa.plano_id = plano["id"]
    db.commit()

    return empresa, headers_super


def test_singleton_e_criado_automaticamente(db):
    assert db.query(ConfiguracaoPlataforma).count() == 0
    config = obter_configuracao_plataforma(db)
    assert config.modo_cobranca == ModoCobranca.AUTOMATICA
    assert db.query(ConfiguracaoPlataforma).count() == 1

    # Chamar de novo não duplica a linha.
    config2 = obter_configuracao_plataforma(db)
    assert config2.id == config.id
    assert db.query(ConfiguracaoPlataforma).count() == 1


def test_provider_plataforma_manual_e_desativada():
    plataforma_manual = ConfiguracaoPlataforma(modo_cobranca=ModoCobranca.MANUAL)
    assert isinstance(obter_provider(plataforma=plataforma_manual), PagamentoPendenteManualProvider)
    assert modo_simulado(plataforma=plataforma_manual) is True

    plataforma_desativada = ConfiguracaoPlataforma(modo_cobranca=ModoCobranca.DESATIVADA, mercadopago_access_token="IGNORADO")
    assert isinstance(obter_provider(plataforma=plataforma_desativada), PagamentoManualProvider)
    assert modo_simulado(plataforma=plataforma_desativada) is False


def test_configurar_cobranca_da_plataforma_via_api(client, db):
    super_admin = criar_super_admin(db, "CP1")
    headers = auth_header(login(client, super_admin["email"], super_admin["senha"]))

    inicial = client.get("/api/plataforma/cobranca", headers=headers).json()
    assert inicial["modo_cobranca"] == "automatica"
    assert inicial["mercadopago_configurado"] is False

    resposta = client.patch(
        "/api/plataforma/cobranca",
        json={"modo_cobranca": "manual", "mercadopago_access_token": "TOKEN-PLATAFORMA", "mercadopago_public_key": "chave"},
        headers=headers,
    )
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["modo_cobranca"] == "manual"
    assert corpo["mercadopago_configurado"] is True
    assert corpo["mercadopago_public_key"] == "chave"
    assert "mercadopago_access_token" not in corpo


def test_configurar_taxa_de_transacao_opcional(client, db):
    super_admin = criar_super_admin(db, "CP5")
    headers = auth_header(login(client, super_admin["email"], super_admin["senha"]))

    inicial = client.get("/api/plataforma/cobranca", headers=headers).json()
    assert inicial["taxa_transacao_percentual"] is None

    resposta = client.patch("/api/plataforma/cobranca", json={"taxa_transacao_percentual": 2.5}, headers=headers)
    assert resposta.status_code == 200
    assert resposta.json()["taxa_transacao_percentual"] == 2.5

    # Zero/vazio desliga de novo.
    removida = client.patch("/api/plataforma/cobranca", json={"taxa_transacao_percentual": None}, headers=headers)
    assert removida.status_code == 200
    assert removida.json()["taxa_transacao_percentual"] is None


def test_admin_empresa_nao_configura_cobranca_da_plataforma(client, db):
    empresa = criar_empresa_completa(db, "CP2")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    resposta = client.get("/api/plataforma/cobranca", headers=headers)
    assert resposta.status_code == 403


def test_fatura_em_modo_manual_fica_pendente_ate_confirmar(client, db):
    empresa, headers_super = _empresa_com_plano(client, db, "CP3")
    client.patch("/api/plataforma/cobranca", json={"modo_cobranca": "manual"}, headers=headers_super)

    fatura_id = client.post(f"/api/empresas/{empresa['empresa_id']}/faturas", headers=headers_super).json()["id"]

    headers_empresa = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    pagar = client.post(f"/api/faturas/{fatura_id}/pagar", headers=headers_empresa)
    assert pagar.status_code == 200
    assert pagar.json()["status"] == "pendente"

    confirmar = client.post(f"/api/faturas/{fatura_id}/confirmar-simulado", headers=headers_empresa)
    assert confirmar.status_code == 200
    assert confirmar.json()["status"] == "paga"


def test_fatura_em_modo_desativada_e_paga_na_hora(client, db):
    empresa, headers_super = _empresa_com_plano(client, db, "CP4")
    client.patch("/api/plataforma/cobranca", json={"modo_cobranca": "desativada"}, headers=headers_super)

    fatura_id = client.post(f"/api/empresas/{empresa['empresa_id']}/faturas", headers=headers_super).json()["id"]

    headers_empresa = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    pagar = client.post(f"/api/faturas/{fatura_id}/pagar", headers=headers_empresa)
    assert pagar.status_code == 200
    assert pagar.json()["status"] == "paga"


def test_pagar_fatura_com_cartao_simulado_aprova_na_hora(client, db):
    empresa, headers_super = _empresa_com_plano(client, db, "CP6")
    fatura_id = client.post(f"/api/empresas/{empresa['empresa_id']}/faturas", headers=headers_super).json()["id"]

    headers_empresa = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    pagar = client.post(
        f"/api/faturas/{fatura_id}/pagar",
        json={"forma_pagamento": "cartao", "mp_token": "TOK", "mp_payment_method_id": "visa"},
        headers=headers_empresa,
    )
    assert pagar.status_code == 200, pagar.text
    corpo = pagar.json()
    assert corpo["status"] == "paga"
    assert corpo["forma_pagamento"] == "cartao"


def test_pagar_fatura_com_boleto_simulado_fica_pendente(client, db):
    empresa, headers_super = _empresa_com_plano(client, db, "CP7")
    fatura_id = client.post(f"/api/empresas/{empresa['empresa_id']}/faturas", headers=headers_super).json()["id"]

    headers_empresa = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    pagar = client.post(
        f"/api/faturas/{fatura_id}/pagar",
        json={"forma_pagamento": "boleto"},
        headers=headers_empresa,
    )
    assert pagar.status_code == 200, pagar.text
    corpo = pagar.json()
    assert corpo["status"] == "pendente"
    assert corpo["forma_pagamento"] == "boleto"
    assert corpo["boleto_codigo_barras"]

    confirmar = client.post(f"/api/faturas/{fatura_id}/confirmar-simulado", headers=headers_empresa)
    assert confirmar.status_code == 200
    assert confirmar.json()["status"] == "paga"


def test_pagamento_simulado_fica_falso_com_gateway_real_configurado(client, db):
    empresa, headers_super = _empresa_com_plano(client, db, "CP8")
    fatura_id = client.post(f"/api/empresas/{empresa['empresa_id']}/faturas", headers=headers_super).json()["id"]

    resposta_antes = client.get("/api/faturas/minhas", headers=auth_header(login(client, empresa["admin_email"], empresa["senha"])))
    assert resposta_antes.json()[0]["pagamento_simulado"] is True

    client.patch(
        "/api/plataforma/cobranca",
        json={"mercadopago_access_token": "TOKEN-REAL", "mercadopago_public_key": "chave-publica"},
        headers=headers_super,
    )

    headers_empresa = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    resposta_depois = client.get("/api/faturas/minhas", headers=headers_empresa)
    assert resposta_depois.json()[0]["pagamento_simulado"] is False


def test_chave_publica_mercadopago_visivel_pro_admin_da_empresa(client, db):
    empresa, headers_super = _empresa_com_plano(client, db, "CP9")
    client.patch("/api/plataforma/cobranca", json={"mercadopago_public_key": "chave-publica-xyz"}, headers=headers_super)

    headers_empresa = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    resposta = client.get("/api/plataforma/chave-publica-mercadopago", headers=headers_empresa)
    assert resposta.status_code == 200
    assert resposta.json()["public_key"] == "chave-publica-xyz"
