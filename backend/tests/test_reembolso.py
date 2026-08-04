from tests.helpers import auth_header, criar_empresa_completa, login


def _vender_e_cancelar(client, headers, viagem_id):
    mapa = client.get(f"/api/viagens/{viagem_id}/poltronas", headers=headers).json()
    poltrona_id = mapa[0]["poltrona_viagem_id"]

    venda = client.post(
        f"/api/viagens/{viagem_id}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": "Fulano",
            "cliente_documento": "000.000.000-00",
            "forma_pagamento": "pix",
        },
        headers=headers,
    ).json()

    client.post(f"/api/viagens/{viagem_id}/passagens/{venda['id']}/cancelar", headers=headers)
    return venda["id"]


def test_reembolso_parcial_e_bloqueio_de_reembolso_duplicado(client, db):
    empresa = criar_empresa_completa(db, "R1")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    passagem_id = _vender_e_cancelar(client, headers, empresa["viagem_id"])

    r1 = client.post(
        f"/api/viagens/{empresa['viagem_id']}/passagens/{passagem_id}/reembolsar",
        json={"motivo": "Desistência", "valor": 40.0},
        headers=headers,
    )
    assert r1.status_code == 200
    assert r1.json()["valor_reembolsado"] == 40.0

    r2 = client.post(
        f"/api/viagens/{empresa['viagem_id']}/passagens/{passagem_id}/reembolsar",
        json={"motivo": "Tentativa duplicada"},
        headers=headers,
    )
    assert r2.status_code == 409


def test_nao_reembolsa_passagem_ainda_confirmada(client, db):
    empresa = criar_empresa_completa(db, "R2")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    mapa = client.get(f"/api/viagens/{empresa['viagem_id']}/poltronas", headers=headers).json()
    poltrona_id = mapa[0]["poltrona_viagem_id"]
    venda = client.post(
        f"/api/viagens/{empresa['viagem_id']}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": "Fulano",
            "cliente_documento": "000.000.000-00",
            "forma_pagamento": "pix",
        },
        headers=headers,
    ).json()

    resposta = client.post(
        f"/api/viagens/{empresa['viagem_id']}/passagens/{venda['id']}/reembolsar",
        json={"motivo": "Teste"},
        headers=headers,
    )
    assert resposta.status_code == 409
