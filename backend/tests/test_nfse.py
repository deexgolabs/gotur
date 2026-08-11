from tests.helpers import auth_header, criar_empresa_completa, login


def test_emitir_nfse_sem_agregador_configurado_fica_simulada(client, db):
    empresa = criar_empresa_completa(db, "NFSE1")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    mapa = client.get(f"/api/viagens/{empresa['viagem_id']}/poltronas", headers=headers).json()
    poltrona_id = next(p["poltrona_viagem_id"] for p in mapa if p["status"] == "livre")
    venda = client.post(
        f"/api/viagens/{empresa['viagem_id']}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": "Fulano",
            "cliente_documento": "000.000.000-00",
            "forma_pagamento": "cartao",
        },
        headers=headers,
    )
    assert venda.status_code == 201, venda.text
    passagem_id = venda.json()["passagem"]["id"]

    resposta = client.post(f"/api/viagens/{empresa['viagem_id']}/passagens/{passagem_id}/nfse", headers=headers)
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert dados["status"] == "simulada"
    assert dados["numero"] is None


def test_emitir_nfse_passagem_de_outra_empresa_da_404(client, db):
    empresa_a = criar_empresa_completa(db, "NFSE2")
    empresa_b = criar_empresa_completa(db, "NFSE3")
    headers_a = auth_header(login(client, empresa_a["admin_email"], empresa_a["senha"]))
    headers_b = auth_header(login(client, empresa_b["admin_email"], empresa_b["senha"]))

    mapa = client.get(f"/api/viagens/{empresa_a['viagem_id']}/poltronas", headers=headers_a).json()
    poltrona_id = next(p["poltrona_viagem_id"] for p in mapa if p["status"] == "livre")
    venda = client.post(
        f"/api/viagens/{empresa_a['viagem_id']}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": "Fulano",
            "cliente_documento": "000.000.000-00",
            "forma_pagamento": "cartao",
        },
        headers=headers_a,
    )
    passagem_id = venda.json()["passagem"]["id"]

    resposta = client.post(f"/api/viagens/{empresa_a['viagem_id']}/passagens/{passagem_id}/nfse", headers=headers_b)
    assert resposta.status_code == 404
