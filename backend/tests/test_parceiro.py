from tests.helpers import auth_header, criar_empresa_completa, login


def _criar_parceiro(client, headers, **overrides):
    dados = {"nome": "Agência Palmas", "documento": "000.111.222-33", "contato": "(63) 99999-0000"}
    dados.update(overrides)
    resposta = client.post("/api/parceiros", json=dados, headers=headers)
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


def test_criar_e_listar_parceiro(client, db):
    empresa = criar_empresa_completa(db, "PAR1")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    parceiro = _criar_parceiro(client, headers)
    assert parceiro["nome"] == "Agência Palmas"
    assert parceiro["ativo"] is True
    assert parceiro["tem_acesso"] is False

    lista = client.get("/api/parceiros", headers=headers).json()
    assert len(lista) == 1
    assert lista[0]["id"] == parceiro["id"]


def test_editar_e_desativar_parceiro(client, db):
    empresa = criar_empresa_completa(db, "PAR2")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    parceiro = _criar_parceiro(client, headers)

    resposta = client.patch(f"/api/parceiros/{parceiro['id']}", json={"ativo": False}, headers=headers)
    assert resposta.status_code == 200
    assert resposta.json()["ativo"] is False

    lista_ativos = client.get("/api/parceiros?apenas_ativos=true", headers=headers).json()
    assert lista_ativos == []


def test_criar_acesso_de_parceiro_permite_login(client, db):
    empresa = criar_empresa_completa(db, "PAR3")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    parceiro = _criar_parceiro(client, headers)

    resposta = client.post(
        f"/api/parceiros/{parceiro['id']}/acesso",
        json={"email": "parceiro.par3@teste.com", "senha": "senha123"},
        headers=headers,
    )
    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["tem_acesso"] is True

    token_parceiro = login(client, "parceiro.par3@teste.com", "senha123")
    assert token_parceiro


def test_venda_de_passagem_com_parceiro_e_dados_extras(client, db):
    empresa = criar_empresa_completa(db, "PAR4")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    parceiro = _criar_parceiro(client, headers)

    resposta = _vender_passagem(
        client,
        headers,
        empresa["viagem_id"],
        parceiro_id=parceiro["id"],
        cliente_telefone="(63) 98888-1234",
        tipo_documento="rg",
        categoria_passageiro="idoso",
    )
    assert resposta.status_code == 201, resposta.text
    passagem = resposta.json()["passagem"]
    assert passagem["parceiro_id"] == parceiro["id"]
    assert passagem["cliente_telefone"] == "(63) 98888-1234"
    assert passagem["tipo_documento"] == "rg"
    assert passagem["categoria_passageiro"] == "idoso"


def test_venda_com_parceiro_de_outra_empresa_e_rejeitada(client, db):
    empresa_a = criar_empresa_completa(db, "PAR5")
    empresa_b = criar_empresa_completa(db, "PAR6")
    headers_a = auth_header(login(client, empresa_a["admin_email"], empresa_a["senha"]))
    headers_b = auth_header(login(client, empresa_b["admin_email"], empresa_b["senha"]))
    parceiro_b = _criar_parceiro(client, headers_b)

    resposta = _vender_passagem(client, headers_a, empresa_a["viagem_id"], parceiro_id=parceiro_b["id"])
    assert resposta.status_code == 400


def test_criar_frete_com_parceiro_e_dados_de_produto(client, db):
    empresa = criar_empresa_completa(db, "PAR7")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    parceiro = _criar_parceiro(client, headers)

    resposta = client.post(
        "/api/fretes",
        json={
            "remetente_nome": "Loja X",
            "destinatario_nome": "Cliente Y",
            "origem": "São Paulo",
            "destino": "Campos do Jordão",
            "data_hora_coleta": "2026-09-01T06:00:00",
            "peso_kg": 12.5,
            "quantidade_volumes": 3,
            "valor_declarado": 500.0,
            "parceiro_id": parceiro["id"],
        },
        headers=headers,
    )
    assert resposta.status_code == 201, resposta.text
    frete = resposta.json()
    assert frete["peso_kg"] == 12.5
    assert frete["quantidade_volumes"] == 3
    assert frete["valor_declarado"] == 500.0
    assert frete["parceiro_id"] == parceiro["id"]


def test_criar_frete_com_parceiro_que_nao_despacha_frete_e_rejeitado(client, db):
    empresa = criar_empresa_completa(db, "PAR8")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    parceiro = _criar_parceiro(client, headers, despacha_frete=False)

    resposta = client.post(
        "/api/fretes",
        json={
            "remetente_nome": "Loja X",
            "destinatario_nome": "Cliente Y",
            "origem": "A",
            "destino": "B",
            "data_hora_coleta": "2026-09-01T06:00:00",
            "parceiro_id": parceiro["id"],
        },
        headers=headers,
    )
    assert resposta.status_code == 400


def test_criar_fretamento_com_parceiro(client, db):
    empresa = criar_empresa_completa(db, "PAR9")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    parceiro = _criar_parceiro(client, headers)

    resposta = client.post(
        "/api/fretamentos",
        json={
            "cliente_nome": "Cliente Fretamento",
            "origem": "A",
            "destino": "B",
            "data_hora_saida": "2026-09-01T06:00:00",
            "parceiro_id": parceiro["id"],
        },
        headers=headers,
    )
    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["parceiro_id"] == parceiro["id"]


def test_parceiro_ve_resumo_e_vendas_isoladas_por_parceiro(client, db):
    empresa = criar_empresa_completa(db, "PAR10", total_poltronas=4)
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    parceiro_a = _criar_parceiro(client, headers_admin, nome="Parceiro A", comissao_percentual=10)
    parceiro_b = _criar_parceiro(client, headers_admin, nome="Parceiro B")

    client.post(
        f"/api/parceiros/{parceiro_a['id']}/acesso",
        json={"email": "acesso.a.par10@teste.com", "senha": "senha123"},
        headers=headers_admin,
    )

    _vender_passagem(client, headers_admin, empresa["viagem_id"], parceiro_id=parceiro_a["id"], cliente_documento="111")
    _vender_passagem(client, headers_admin, empresa["viagem_id"], parceiro_id=parceiro_b["id"], cliente_documento="222")
    _vender_passagem(client, headers_admin, empresa["viagem_id"], cliente_documento="333")  # venda direta, sem parceiro

    token_parceiro_a = login(client, "acesso.a.par10@teste.com", "senha123")
    headers_parceiro_a = auth_header(token_parceiro_a)

    resumo = client.get("/api/parceiros/minha/resumo", headers=headers_parceiro_a).json()
    assert resumo["total_passagens"] == 1
    assert resumo["total_arrecadado_passagens"] == 100.0
    assert resumo["comissao_estimada"] == 10.0

    minhas_passagens = client.get("/api/parceiros/minha/passagens", headers=headers_parceiro_a).json()
    assert len(minhas_passagens) == 1
    assert minhas_passagens[0]["cliente_documento"] == "111"


def test_relatorio_por_parceiro(client, db):
    empresa = criar_empresa_completa(db, "PAR12")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    parceiro = _criar_parceiro(client, headers, comissao_percentual=5)

    _vender_passagem(client, headers, empresa["viagem_id"], parceiro_id=parceiro["id"])

    linhas = client.get("/api/relatorios/parceiros", headers=headers).json()
    assert len(linhas) == 1
    assert linhas[0]["parceiro_id"] == parceiro["id"]
    assert linhas[0]["total_passagens"] == 1
    assert linhas[0]["total_arrecadado_passagens"] == 100.0
    assert linhas[0]["comissao_estimada"] == 5.0


def test_parceiro_nao_acessa_rotas_de_staff(client, db):
    empresa = criar_empresa_completa(db, "PAR11")
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    parceiro = _criar_parceiro(client, headers_admin)
    client.post(
        f"/api/parceiros/{parceiro['id']}/acesso",
        json={"email": "acesso.par11@teste.com", "senha": "senha123"},
        headers=headers_admin,
    )
    headers_parceiro = auth_header(login(client, "acesso.par11@teste.com", "senha123"))

    resposta = client.get("/api/parceiros", headers=headers_parceiro)
    assert resposta.status_code == 403

    resposta_venda = client.get(f"/api/viagens/{empresa['viagem_id']}/passagens", headers=headers_parceiro)
    assert resposta_venda.status_code == 403
