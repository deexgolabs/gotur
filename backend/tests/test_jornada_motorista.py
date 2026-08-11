from tests.helpers import auth_header, criar_empresa_completa, login


def test_iniciar_e_encerrar_jornada(client, db):
    empresa = criar_empresa_completa(db, "JOR1")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    iniciada = client.post(
        "/api/jornadas",
        json={"motorista_nome": "João Motorista", "tipo_viagem": "viagem", "referencia_id": empresa["viagem_id"]},
        headers=headers,
    )
    assert iniciada.status_code == 201, iniciada.text
    jornada = iniciada.json()
    assert jornada["fim"] is None
    assert jornada["horas"] >= 0

    encerrada = client.patch(f"/api/jornadas/{jornada['id']}/encerrar", headers=headers)
    assert encerrada.status_code == 200
    assert encerrada.json()["fim"] is not None

    repetir = client.patch(f"/api/jornadas/{jornada['id']}/encerrar", headers=headers)
    assert repetir.status_code == 400


def test_listar_jornadas_filtra_por_motorista_e_referencia(client, db):
    empresa = criar_empresa_completa(db, "JOR2")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    client.post(
        "/api/jornadas",
        json={"motorista_nome": "Ana Motorista", "tipo_viagem": "viagem", "referencia_id": empresa["viagem_id"]},
        headers=headers,
    )
    client.post(
        "/api/jornadas",
        json={"motorista_nome": "Outro Motorista", "tipo_viagem": "viagem", "referencia_id": empresa["viagem_id"]},
        headers=headers,
    )

    lista = client.get("/api/jornadas?motorista_nome=Ana Motorista", headers=headers).json()
    assert len(lista) == 1
    assert lista[0]["motorista_nome"] == "Ana Motorista"

    por_referencia = client.get(
        f"/api/jornadas?tipo_viagem=viagem&referencia_id={empresa['viagem_id']}", headers=headers
    ).json()
    assert len(por_referencia) == 2


def test_resumo_de_jornada_acusa_acima_do_limite_com_muitas_jornadas_abertas(client, db):
    empresa = criar_empresa_completa(db, "JOR3")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    # 3 jornadas em aberto pro mesmo motorista, cada uma conta o tempo
    # desde o início até "agora" — mesmo que sejam alguns milissegundos
    # cada, o resumo não deve estourar sem motivo.
    for _ in range(3):
        client.post(
            "/api/jornadas",
            json={"motorista_nome": "Carlos Motorista", "tipo_viagem": "frete", "referencia_id": 1},
            headers=headers,
        )

    resumo = client.get("/api/jornadas/resumo?motorista_nome=Carlos Motorista", headers=headers).json()
    assert "horas_ultimas_24h" in resumo
    assert resumo["horas_ultimas_24h"] >= 0
    assert resumo["acima_do_limite"] is False


def test_jornada_de_outra_empresa_nao_pode_ser_encerrada(client, db):
    empresa_a = criar_empresa_completa(db, "JOR4")
    empresa_b = criar_empresa_completa(db, "JOR5")
    headers_a = auth_header(login(client, empresa_a["admin_email"], empresa_a["senha"]))
    headers_b = auth_header(login(client, empresa_b["admin_email"], empresa_b["senha"]))

    jornada = client.post(
        "/api/jornadas",
        json={"motorista_nome": "Teste", "tipo_viagem": "fretamento", "referencia_id": 1},
        headers=headers_a,
    ).json()

    resposta = client.patch(f"/api/jornadas/{jornada['id']}/encerrar", headers=headers_b)
    assert resposta.status_code == 404

    # empresa_b não vê a jornada de empresa_a na listagem
    lista_b = client.get("/api/jornadas", headers=headers_b).json()
    assert lista_b == []


def test_viagem_aceita_motorista_nome(client, db):
    empresa = criar_empresa_completa(db, "JOR6")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    resposta = client.patch(
        f"/api/viagens/{empresa['viagem_id']}", json={"motorista_nome": "Pedro Motorista"}, headers=headers
    )
    assert resposta.status_code == 200
    assert resposta.json()["motorista_nome"] == "Pedro Motorista"
