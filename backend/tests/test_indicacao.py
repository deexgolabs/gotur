from app.models.usuario import Usuario
from tests.helpers import auth_header, criar_cliente, criar_empresa_completa, login


def _registrar_cliente(client, db, sufixo: str):
    cliente = criar_cliente(db, sufixo)
    return auth_header(login(client, cliente["email"], cliente["senha"]))


def _id_por_email(db, email: str) -> int:
    return db.query(Usuario).filter(Usuario.email == email).first().id


def _vincular_indicacao(db, indicado_email: str, indicador_id: int) -> None:
    indicado = db.query(Usuario).filter(Usuario.email == indicado_email).first()
    indicado.indicado_por_usuario_id = indicador_id
    db.commit()


def _comprar(client, headers, viagem_id):
    mapa = client.get(f"/api/viagens/{viagem_id}/poltronas", headers=headers).json()
    poltrona_id = next(p["poltrona_viagem_id"] for p in mapa if p["status"] == "livre")
    resposta = client.post(
        f"/api/viagens/{viagem_id}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": "Cliente Indicado",
            "cliente_documento": "777.777.777-77",
            "forma_pagamento": "cartao",
        },
        headers=headers,
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["passagem"]


def _ativar_indicacao(client, headers_admin, **overrides):
    dados = {"indicacao_ativa": True, "indicacao_desconto_percentual": 15}
    dados.update(overrides)
    resposta = client.patch("/api/empresas/minha/indicacao", json=dados, headers=headers_admin)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_indicado_e_indicador_ganham_cupom_na_primeira_compra_do_indicado(client, db):
    empresa = criar_empresa_completa(db, "IND1", total_poltronas=4)
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    _ativar_indicacao(client, headers_admin)

    indicador = criar_cliente(db, "ind1a")
    indicado = criar_cliente(db, "ind1b")
    _vincular_indicacao(db, indicado["email"], _id_por_email(db, indicador["email"]))

    headers_indicado = auth_header(login(client, indicado["email"], indicado["senha"]))
    headers_indicador = auth_header(login(client, indicador["email"], indicador["senha"]))

    _comprar(client, headers_indicado, empresa["viagem_id"])

    cupons_indicado = client.get("/api/cupons/minhas", headers=headers_indicado).json()
    cupons_indicador = client.get("/api/cupons/minhas", headers=headers_indicador).json()
    assert len(cupons_indicado) == 1
    assert len(cupons_indicador) == 1
    assert cupons_indicado[0]["valor"] == 15.0
    assert cupons_indicador[0]["valor"] == 15.0
    assert cupons_indicado[0]["codigo"].startswith("INDICACAO")
    assert cupons_indicado[0]["codigo"] != cupons_indicador[0]["codigo"]


def test_segunda_compra_do_indicado_nao_gera_cupom_de_novo(client, db):
    empresa = criar_empresa_completa(db, "IND2", total_poltronas=4)
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    _ativar_indicacao(client, headers_admin)

    indicador = criar_cliente(db, "ind2a")
    indicado = criar_cliente(db, "ind2b")
    _vincular_indicacao(db, indicado["email"], _id_por_email(db, indicador["email"]))

    headers_indicado = auth_header(login(client, indicado["email"], indicado["senha"]))
    _comprar(client, headers_indicado, empresa["viagem_id"])
    _comprar(client, headers_indicado, empresa["viagem_id"])

    cupons = client.get("/api/cupons/minhas", headers=headers_indicado).json()
    assert len(cupons) == 1


def test_indicacao_desligada_nao_gera_cupom(client, db):
    empresa = criar_empresa_completa(db, "IND3", total_poltronas=4)
    # não ativa o programa

    indicador = criar_cliente(db, "ind3a")
    indicado = criar_cliente(db, "ind3b")
    _vincular_indicacao(db, indicado["email"], _id_por_email(db, indicador["email"]))

    headers_indicado = auth_header(login(client, indicado["email"], indicado["senha"]))
    _comprar(client, headers_indicado, empresa["viagem_id"])

    cupons = client.get("/api/cupons/minhas", headers=headers_indicado).json()
    assert cupons == []


def test_cliente_sem_indicador_nao_gera_cupom(client, db):
    empresa = criar_empresa_completa(db, "IND4", total_poltronas=4)
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    _ativar_indicacao(client, headers_admin)

    headers_cliente = _registrar_cliente(client, db, "ind4")
    _comprar(client, headers_cliente, empresa["viagem_id"])

    cupons = client.get("/api/cupons/minhas", headers=headers_cliente).json()
    assert cupons == []


def test_meu_perfil_gera_codigo_de_indicacao_na_primeira_consulta(client, db):
    cliente = criar_cliente(db, "IND5")
    headers = auth_header(login(client, cliente["email"], cliente["senha"]))

    perfil1 = client.get("/api/usuarios/me", headers=headers).json()
    assert perfil1["codigo_indicacao"]

    perfil2 = client.get("/api/usuarios/me", headers=headers).json()
    assert perfil2["codigo_indicacao"] == perfil1["codigo_indicacao"]


def test_cadastro_publico_com_codigo_de_indicacao_valido(client, db):
    indicador = criar_cliente(db, "IND6")
    headers_indicador = auth_header(login(client, indicador["email"], indicador["senha"]))
    codigo = client.get("/api/usuarios/me", headers=headers_indicador).json()["codigo_indicacao"]
    indicador_id = _id_por_email(db, indicador["email"])

    resposta = client.post(
        "/api/auth/registrar-cliente",
        json={
            "nome": "Novo Cliente",
            "email": "novocliente.ind6@teste.com",
            "senha": "senha123",
            "documento": "888.888.888-88",
            "codigo_indicacao": codigo,
        },
    )
    assert resposta.status_code == 201, resposta.text

    novo = db.query(Usuario).filter(Usuario.email == "novocliente.ind6@teste.com").first()
    assert novo.indicado_por_usuario_id == indicador_id


def test_cadastro_publico_com_codigo_de_indicacao_invalido_nao_quebra(client, db):
    resposta = client.post(
        "/api/auth/registrar-cliente",
        json={
            "nome": "Outro Cliente",
            "email": "outrocliente.ind7@teste.com",
            "senha": "senha123",
            "documento": "999.999.999-99",
            "codigo_indicacao": "NAOEXISTE",
        },
    )
    assert resposta.status_code == 201, resposta.text
    novo = db.query(Usuario).filter(Usuario.email == "outrocliente.ind7@teste.com").first()
    assert novo.indicado_por_usuario_id is None
