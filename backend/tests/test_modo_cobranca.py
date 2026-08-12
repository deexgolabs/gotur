from app.models.empresa import Empresa
from app.models.enums import ModoCobranca
from app.services.pagamento_provider import (
    PagamentoManualProvider,
    PagamentoPendenteManualProvider,
    modo_simulado,
    obter_provider,
)
from tests.helpers import auth_header, criar_empresa_completa, login


def _poltrona_livre(client, headers, viagem_id):
    mapa = client.get(f"/api/viagens/{viagem_id}/poltronas", headers=headers).json()
    return next(p for p in mapa if p["status"] == "livre")["poltrona_viagem_id"]


def _comprar(client, headers, viagem_id, poltrona_id, forma_pagamento):
    return client.post(
        f"/api/viagens/{viagem_id}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": "Fulano",
            "cliente_documento": "000.000.000-00",
            "forma_pagamento": forma_pagamento,
        },
        headers=headers,
    )


def test_provider_manual_ignora_forma_de_pagamento_sempre_pendente():
    empresa = Empresa(nome="X", cnpj="1", modo_cobranca=ModoCobranca.MANUAL)
    provider = obter_provider(empresa)
    assert isinstance(provider, PagamentoPendenteManualProvider)
    for forma in ("pix", "cartao", "dinheiro"):
        resultado = provider.cobrar(forma_pagamento=forma, valor=50.0, referencia_pedido="ref")
        assert resultado.status == "pendente"
    assert modo_simulado(empresa) is True


def test_provider_desativada_aprova_tudo_na_hora():
    empresa = Empresa(nome="X", cnpj="1", modo_cobranca=ModoCobranca.DESATIVADA, mercadopago_access_token="TOKEN-QUE-DEVE-SER-IGNORADO")
    provider = obter_provider(empresa)
    assert isinstance(provider, PagamentoManualProvider)
    for forma in ("pix", "cartao", "dinheiro"):
        resultado = provider.cobrar(forma_pagamento=forma, valor=50.0, referencia_pedido="ref")
        assert resultado.status == "aprovado"
    assert modo_simulado(empresa) is False


def test_configurar_modo_cobranca_via_api(client, db):
    empresa = criar_empresa_completa(db, "MC1")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    inicial = client.get("/api/empresas/minha", headers=headers).json()
    assert inicial["modo_cobranca"] == "automatica"

    resposta = client.patch("/api/empresas/minha/pagamento", json={"modo_cobranca": "desativada"}, headers=headers)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["modo_cobranca"] == "desativada"


def test_venda_em_modo_manual_fica_pendente_mesmo_no_dinheiro(client, db):
    empresa = criar_empresa_completa(db, "MC2")
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    client.patch("/api/empresas/minha/pagamento", json={"modo_cobranca": "manual"}, headers=headers_admin)

    headers_func = auth_header(login(client, empresa["funcionario_email"], empresa["senha"]))
    poltrona_id = _poltrona_livre(client, headers_func, empresa["viagem_id"])

    resposta = _comprar(client, headers_func, empresa["viagem_id"], poltrona_id, "dinheiro")
    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["passagem"] is None
    assert corpo["pedido_pagamento"]["status"] == "pendente"

    confirmar = client.post(f"/api/pedidos-pagamento/{corpo['pedido_pagamento']['id']}/confirmar-simulado", headers=headers_func)
    assert confirmar.status_code == 200, confirmar.text
    assert confirmar.json()["status"] == "confirmada"


def test_venda_em_modo_desativada_aprova_na_hora_mesmo_no_pix(client, db):
    empresa = criar_empresa_completa(db, "MC3")
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    client.patch("/api/empresas/minha/pagamento", json={"modo_cobranca": "desativada"}, headers=headers_admin)

    headers_func = auth_header(login(client, empresa["funcionario_email"], empresa["senha"]))
    poltrona_id = _poltrona_livre(client, headers_func, empresa["viagem_id"])

    resposta = _comprar(client, headers_func, empresa["viagem_id"], poltrona_id, "pix")
    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["pedido_pagamento"] is None
    assert corpo["passagem"]["status"] == "confirmada"


def test_modo_automatica_com_manual_desligado_nao_ganha_permissao_de_confirmar_manual(client, db):
    """Sem token do Mercado Pago e em modo AUTOMATICA (padrão), continua
    igual a antes: cai pro simulado, confirmação manual liberada porque não
    tem gateway real configurado — não por causa do modo de cobrança."""
    empresa = criar_empresa_completa(db, "MC4")
    headers_func = auth_header(login(client, empresa["funcionario_email"], empresa["senha"]))
    poltrona_id = _poltrona_livre(client, headers_func, empresa["viagem_id"])

    resposta = _comprar(client, headers_func, empresa["viagem_id"], poltrona_id, "pix")
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["pedido_pagamento"]["status"] == "pendente"

    confirmar = client.post(f"/api/pedidos-pagamento/{corpo['pedido_pagamento']['id']}/confirmar-simulado", headers=headers_func)
    assert confirmar.status_code == 200
