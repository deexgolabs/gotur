from tests.helpers import auth_header, criar_empresa_completa, login


def _vender_passagem(client, headers, viagem_id, **overrides):
    mapa = client.get(f"/api/viagens/{viagem_id}/poltronas", headers=headers).json()
    poltrona_id = next(p["poltrona_viagem_id"] for p in mapa if p["status"] == "livre")
    dados = {
        "poltrona_viagem_id": poltrona_id,
        "cliente_nome": "Fulano de Tal",
        "cliente_documento": "000.000.000-00",
        "forma_pagamento": "cartao",
    }
    dados.update(overrides)
    return client.post(f"/api/viagens/{viagem_id}/passagens", json=dados, headers=headers)


def test_manifesto_pdf_gerado_com_passageiros_confirmados(client, db):
    empresa = criar_empresa_completa(db, "MAN1")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    resposta_venda = _vender_passagem(client, headers, empresa["viagem_id"])
    assert resposta_venda.status_code == 201, resposta_venda.text

    resposta = client.get(f"/api/viagens/{empresa['viagem_id']}/manifesto.pdf", headers=headers)
    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "application/pdf"
    assert resposta.content[:4] == b"%PDF"


def test_manifesto_pdf_de_viagem_de_outra_empresa_e_rejeitado(client, db):
    empresa_a = criar_empresa_completa(db, "MAN2")
    empresa_b = criar_empresa_completa(db, "MAN3")
    headers_a = auth_header(login(client, empresa_a["admin_email"], empresa_a["senha"]))

    resposta = client.get(f"/api/viagens/{empresa_b['viagem_id']}/manifesto.pdf", headers=headers_a)
    assert resposta.status_code == 404


def test_viagem_sem_passageiros_gera_manifesto_vazio(client, db):
    empresa = criar_empresa_completa(db, "MAN4")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    resposta = client.get(f"/api/viagens/{empresa['viagem_id']}/manifesto.pdf", headers=headers)
    assert resposta.status_code == 200
    assert resposta.content[:4] == b"%PDF"
