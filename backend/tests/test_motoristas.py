from datetime import datetime, timedelta

from tests.helpers import auth_header, criar_empresa_completa, login


def test_criar_listar_e_editar_motorista(client, db):
    empresa = criar_empresa_completa(db, "MOT1")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    criado = client.post(
        "/api/motoristas",
        json={"nome": "João Silva", "cnh": "12345678900", "categoria_cnh": "d", "telefone": "62999990000"},
        headers=headers,
    )
    assert criado.status_code == 201, criado.text
    motorista = criado.json()
    assert motorista["nome"] == "João Silva"
    assert motorista["categoria_cnh"] == "d"
    assert motorista["ativo"] is True

    lista = client.get("/api/motoristas", headers=headers)
    assert lista.status_code == 200
    assert any(m["id"] == motorista["id"] for m in lista.json())

    editado = client.patch(f"/api/motoristas/{motorista['id']}", json={"telefone": "62988880000", "ativo": False}, headers=headers)
    assert editado.status_code == 200
    assert editado.json()["telefone"] == "62988880000"
    assert editado.json()["ativo"] is False

    apenas_ativos = client.get("/api/motoristas?apenas_ativos=true", headers=headers)
    assert all(m["id"] != motorista["id"] for m in apenas_ativos.json())


def test_motorista_de_outra_empresa_e_rejeitado(client, db):
    empresa_a = criar_empresa_completa(db, "MOT2")
    empresa_b = criar_empresa_completa(db, "MOT3")
    headers_a = auth_header(login(client, empresa_a["admin_email"], empresa_a["senha"]))
    headers_b = auth_header(login(client, empresa_b["admin_email"], empresa_b["senha"]))

    criado = client.post("/api/motoristas", json={"nome": "Motorista B"}, headers=headers_b)
    motorista_id = criado.json()["id"]

    resposta = client.patch(f"/api/motoristas/{motorista_id}", json={"nome": "Hackeado"}, headers=headers_a)
    assert resposta.status_code == 404


def test_funcionario_nao_cria_motorista(client, db):
    empresa = criar_empresa_completa(db, "MOT4")
    headers = auth_header(login(client, empresa["funcionario_email"], empresa["senha"]))

    resposta = client.post("/api/motoristas", json={"nome": "Sem Permissao"}, headers=headers)
    assert resposta.status_code == 403


def test_vincular_motorista_id_na_viagem_auto_preenche_nome(client, db):
    empresa = criar_empresa_completa(db, "MOT5")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    motorista = client.post("/api/motoristas", json={"nome": "Carlos Motorista"}, headers=headers).json()

    partida = (datetime.now() + timedelta(days=2)).isoformat()
    criada = client.post(
        "/api/viagens",
        json={
            "rota_id": empresa["rota_id"],
            "onibus_id": empresa["onibus_id"],
            "data_hora_partida": partida,
            "preco": 80.0,
            "motorista_id": motorista["id"],
        },
        headers=headers,
    )
    assert criada.status_code == 201, criada.text
    viagem = criada.json()
    assert viagem["motorista_id"] == motorista["id"]
    assert viagem["motorista_nome"] == "Carlos Motorista"


def test_motorista_id_invalido_na_viagem_e_rejeitado(client, db):
    empresa = criar_empresa_completa(db, "MOT6")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    partida = (datetime.now() + timedelta(days=2)).isoformat()
    resposta = client.post(
        "/api/viagens",
        json={
            "rota_id": empresa["rota_id"],
            "onibus_id": empresa["onibus_id"],
            "data_hora_partida": partida,
            "preco": 80.0,
            "motorista_id": 999999,
        },
        headers=headers,
    )
    assert resposta.status_code == 404


def test_vincular_motorista_id_no_fretamento_auto_preenche_nome(client, db):
    empresa = criar_empresa_completa(db, "MOT7")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    motorista = client.post("/api/motoristas", json={"nome": "Ana Motorista"}, headers=headers).json()

    saida = (datetime.now() + timedelta(days=3)).isoformat()
    criado = client.post(
        "/api/fretamentos",
        json={
            "cliente_nome": "Cliente Teste",
            "origem": "Cidade A",
            "destino": "Cidade B",
            "data_hora_saida": saida,
            "motorista_id": motorista["id"],
        },
        headers=headers,
    )
    assert criado.status_code == 201, criado.text
    fretamento = criado.json()
    assert fretamento["motorista_id"] == motorista["id"]
    assert fretamento["motorista_nome"] == "Ana Motorista"

    editado = client.patch(
        f"/api/fretamentos/{fretamento['id']}",
        json={"motorista_id": None, "motorista_nome": "Texto Livre"},
        headers=headers,
    )
    assert editado.status_code == 200
    assert editado.json()["motorista_id"] is None
    assert editado.json()["motorista_nome"] == "Texto Livre"


def test_vincular_motorista_id_no_frete_auto_preenche_nome(client, db):
    empresa = criar_empresa_completa(db, "MOT8")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    motorista = client.post("/api/motoristas", json={"nome": "Pedro Motorista"}, headers=headers).json()

    coleta = (datetime.now() + timedelta(days=1)).isoformat()
    criado = client.post(
        "/api/fretes",
        json={
            "remetente_nome": "Remetente",
            "destinatario_nome": "Destinatario",
            "origem": "Cidade A",
            "destino": "Cidade B",
            "data_hora_coleta": coleta,
            "motorista_id": motorista["id"],
        },
        headers=headers,
    )
    assert criado.status_code == 201, criado.text
    frete = criado.json()
    assert frete["motorista_id"] == motorista["id"]
    assert frete["motorista_nome"] == "Pedro Motorista"
