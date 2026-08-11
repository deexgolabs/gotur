from tests.helpers import auth_header, criar_empresa_completa, login


def _criar_cupom(client, headers, **overrides):
    dados = {"codigo": "PROMO10", "tipo": "percentual", "valor": 10}
    dados.update(overrides)
    resposta = client.post("/api/cupons", json=dados, headers=headers)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _vender_passagem(client, headers, viagem_id, **overrides):
    mapa = client.get(f"/api/viagens/{viagem_id}/poltronas", headers=headers).json()
    poltrona_id = next(p["poltrona_viagem_id"] for p in mapa if p["status"] == "livre")
    dados = {
        "poltrona_viagem_id": poltrona_id,
        "cliente_nome": "Fulano",
        "cliente_documento": "000.000.000-00",
        "forma_pagamento": "cartao",
    }
    dados.update(overrides)
    return client.post(f"/api/viagens/{viagem_id}/passagens", json=dados, headers=headers)


def test_criar_cupom_e_bloquear_codigo_duplicado(client, db):
    empresa = criar_empresa_completa(db, "CUP1")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    cupom = _criar_cupom(client, headers)
    assert cupom["codigo"] == "PROMO10"
    assert cupom["usos_atuais"] == 0

    duplicado = client.post("/api/cupons", json={"codigo": "promo10", "tipo": "fixo", "valor": 5}, headers=headers)
    assert duplicado.status_code == 409


def test_cupom_percentual_aplica_desconto_na_venda(client, db):
    empresa = criar_empresa_completa(db, "CUP2")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    _criar_cupom(client, headers, codigo="DEZ", tipo="percentual", valor=10)

    resposta = _vender_passagem(client, headers, empresa["viagem_id"], codigo_cupom="dez")
    assert resposta.status_code == 201, resposta.text
    passagem = resposta.json()["passagem"]
    assert passagem["preco"] == 90.0
    assert passagem["codigo_cupom"] == "DEZ"

    cupons = client.get("/api/cupons", headers=headers).json()
    assert cupons[0]["usos_atuais"] == 1


def test_cupom_fixo_nao_deixa_preco_negativo(client, db):
    empresa = criar_empresa_completa(db, "CUP3")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    _criar_cupom(client, headers, codigo="MEGA", tipo="fixo", valor=500)

    resposta = _vender_passagem(client, headers, empresa["viagem_id"], codigo_cupom="MEGA")
    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["passagem"]["preco"] == 0.0


def test_cupom_invalido_e_rejeitado(client, db):
    empresa = criar_empresa_completa(db, "CUP4")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    resposta = _vender_passagem(client, headers, empresa["viagem_id"], codigo_cupom="NAOEXISTE")
    assert resposta.status_code == 400


def test_cupom_desativado_e_rejeitado(client, db):
    empresa = criar_empresa_completa(db, "CUP5")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    cupom = _criar_cupom(client, headers, codigo="OFF", tipo="fixo", valor=10)

    client.patch(f"/api/cupons/{cupom['id']}", json={"ativo": False}, headers=headers)

    resposta = _vender_passagem(client, headers, empresa["viagem_id"], codigo_cupom="OFF")
    assert resposta.status_code == 400


def test_cupom_respeita_limite_de_usos(client, db):
    empresa = criar_empresa_completa(db, "CUP6", total_poltronas=3)
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    _criar_cupom(client, headers, codigo="UMSO", tipo="fixo", valor=10, max_usos=1)

    primeira = _vender_passagem(client, headers, empresa["viagem_id"], codigo_cupom="UMSO", cliente_documento="111")
    assert primeira.status_code == 201, primeira.text

    segunda = _vender_passagem(client, headers, empresa["viagem_id"], codigo_cupom="UMSO", cliente_documento="222")
    assert segunda.status_code == 400


def test_cupom_e_isolado_por_empresa(client, db):
    empresa_a = criar_empresa_completa(db, "CUP7")
    empresa_b = criar_empresa_completa(db, "CUP8")
    headers_a = auth_header(login(client, empresa_a["admin_email"], empresa_a["senha"]))
    headers_b = auth_header(login(client, empresa_b["admin_email"], empresa_b["senha"]))

    _criar_cupom(client, headers_a, codigo="SOA", tipo="fixo", valor=10)

    resposta = _vender_passagem(client, headers_b, empresa_b["viagem_id"], codigo_cupom="SOA")
    assert resposta.status_code == 400
