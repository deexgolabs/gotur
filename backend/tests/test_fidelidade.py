from tests.helpers import auth_header, criar_cliente, criar_empresa_completa, login


def _registrar_cliente(client, db, sufixo: str):
    cliente = criar_cliente(db, sufixo)
    return auth_header(login(client, cliente["email"], cliente["senha"]))


def _comprar(client, headers, viagem_id):
    mapa = client.get(f"/api/viagens/{viagem_id}/poltronas", headers=headers).json()
    poltrona_id = next(p["poltrona_viagem_id"] for p in mapa if p["status"] == "livre")
    resposta = client.post(
        f"/api/viagens/{viagem_id}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": "Cliente Fiel",
            "cliente_documento": "444.444.444-44",
            "forma_pagamento": "cartao",
        },
        headers=headers,
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["passagem"]


def _ativar_fidelidade(client, headers_admin, **overrides):
    dados = {"fidelidade_ativa": True, "fidelidade_passagens_necessarias": 2, "fidelidade_desconto_percentual": 15}
    dados.update(overrides)
    resposta = client.patch("/api/empresas/minha/fidelidade", json=dados, headers=headers_admin)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_fidelidade_gera_cupom_pessoal_apos_n_passagens(client, db):
    empresa = criar_empresa_completa(db, "FID1", total_poltronas=4)
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    _ativar_fidelidade(client, headers_admin)

    headers_cliente = _registrar_cliente(client, db, "fid1")

    _comprar(client, headers_cliente, empresa["viagem_id"])
    sem_cupom = client.get("/api/cupons/minhas", headers=headers_cliente).json()
    assert sem_cupom == []

    _comprar(client, headers_cliente, empresa["viagem_id"])
    com_cupom = client.get("/api/cupons/minhas", headers=headers_cliente).json()
    assert len(com_cupom) == 1
    assert com_cupom[0]["valor"] == 15.0
    assert com_cupom[0]["max_usos"] == 1
    assert com_cupom[0]["codigo"].startswith("FIDELIDADE")


def test_fidelidade_desligada_nao_gera_cupom(client, db):
    empresa = criar_empresa_completa(db, "FID2", total_poltronas=4)
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    # não ativa o programa

    headers_cliente = _registrar_cliente(client, db, "fid2")
    _comprar(client, headers_cliente, empresa["viagem_id"])
    _comprar(client, headers_cliente, empresa["viagem_id"])

    cupons = client.get("/api/cupons/minhas", headers=headers_cliente).json()
    assert cupons == []


def test_venda_de_balcao_sem_conta_nao_gera_cupom_de_fidelidade(client, db):
    empresa = criar_empresa_completa(db, "FID3", total_poltronas=4)
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    _ativar_fidelidade(client, headers_admin, fidelidade_passagens_necessarias=1)

    # funcionário vende pra alguém sem conta (cliente_nome só texto) — não
    # tem cliente_usuario_id, então não pode acumular fidelidade
    mapa = client.get(f"/api/viagens/{empresa['viagem_id']}/poltronas", headers=headers_admin).json()
    poltrona_id = next(p["poltrona_viagem_id"] for p in mapa if p["status"] == "livre")
    resposta = client.post(
        f"/api/viagens/{empresa['viagem_id']}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": "Fulano de Balcão",
            "cliente_documento": "555.555.555-55",
            "forma_pagamento": "dinheiro",
        },
        headers=headers_admin,
    )
    assert resposta.status_code == 201, resposta.text

    lista_cupons = client.get("/api/cupons", headers=headers_admin).json()
    assert lista_cupons == []


def test_cupom_pessoal_nao_pode_ser_usado_por_outro_cliente(client, db):
    empresa = criar_empresa_completa(db, "FID4", total_poltronas=6)
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    _ativar_fidelidade(client, headers_admin, fidelidade_passagens_necessarias=1)

    headers_a = _registrar_cliente(client, db, "fid4a")
    _comprar(client, headers_a, empresa["viagem_id"])

    cupom = client.get("/api/cupons/minhas", headers=headers_a).json()[0]

    headers_b = _registrar_cliente(client, db, "fid4b")
    mapa = client.get(f"/api/viagens/{empresa['viagem_id']}/poltronas", headers=headers_b).json()
    poltrona_id = next(p["poltrona_viagem_id"] for p in mapa if p["status"] == "livre")
    resposta = client.post(
        f"/api/viagens/{empresa['viagem_id']}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": "Cliente B",
            "cliente_documento": "666.666.666-66",
            "forma_pagamento": "cartao",
            "codigo_cupom": cupom["codigo"],
        },
        headers=headers_b,
    )
    assert resposta.status_code == 400
    assert "pessoal" in resposta.json()["detail"]


def test_cupom_pessoal_de_fidelidade_aplica_desconto_pro_dono(client, db):
    empresa = criar_empresa_completa(db, "FID5", total_poltronas=6)
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    _ativar_fidelidade(client, headers_admin, fidelidade_passagens_necessarias=1, fidelidade_desconto_percentual=20)

    headers_cliente = _registrar_cliente(client, db, "fid5")
    _comprar(client, headers_cliente, empresa["viagem_id"])
    cupom = client.get("/api/cupons/minhas", headers=headers_cliente).json()[0]

    mapa = client.get(f"/api/viagens/{empresa['viagem_id']}/poltronas", headers=headers_cliente).json()
    poltrona_id = next(p["poltrona_viagem_id"] for p in mapa if p["status"] == "livre")
    resposta = client.post(
        f"/api/viagens/{empresa['viagem_id']}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": "Cliente Fiel",
            "cliente_documento": "444.444.444-44",
            "forma_pagamento": "cartao",
            "codigo_cupom": cupom["codigo"],
        },
        headers=headers_cliente,
    )
    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["passagem"]["preco"] == 80.0
