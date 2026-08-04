from tests.helpers import auth_header, criar_empresa_completa, login


def test_admin_nao_ve_rotas_de_outra_empresa(client, db):
    empresa_a = criar_empresa_completa(db, "A")
    empresa_b = criar_empresa_completa(db, "B")

    token_a = login(client, empresa_a["admin_email"], empresa_a["senha"])

    resposta = client.get("/api/rotas", headers=auth_header(token_a))
    assert resposta.status_code == 200
    ids_visiveis = {r["id"] for r in resposta.json()}
    assert empresa_a["rota_id"] in ids_visiveis
    assert empresa_b["rota_id"] not in ids_visiveis


def test_admin_nao_edita_onibus_de_outra_empresa(client, db):
    empresa_a = criar_empresa_completa(db, "A")
    empresa_b = criar_empresa_completa(db, "B")
    token_a = login(client, empresa_a["admin_email"], empresa_a["senha"])

    resposta = client.patch(
        f"/api/onibus/{empresa_b['onibus_id']}",
        json={"identificacao": "HACK"},
        headers=auth_header(token_a),
    )
    assert resposta.status_code == 404


def test_funcionario_nao_acessa_rotas_admin_only(client, db):
    empresa = criar_empresa_completa(db, "C")
    token_func = login(client, empresa["funcionario_email"], empresa["senha"])

    resposta = client.post(
        "/api/rotas", json={"origem": "X", "destino": "Y"}, headers=auth_header(token_func)
    )
    assert resposta.status_code == 403
