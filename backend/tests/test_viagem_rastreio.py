from tests.helpers import auth_header, criar_empresa_completa, login


def test_posicoes_gps_viagem_calculam_distancia_percorrida(client, db):
    empresa = criar_empresa_completa(db, "VR1")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    vid = empresa["viagem_id"]

    # São Paulo -> Campinas (~90km em linha reta) em dois pontos.
    client.post(f"/api/viagens/{vid}/posicoes", json={"latitude": -23.5505, "longitude": -46.6333}, headers=headers)
    resposta = client.post(f"/api/viagens/{vid}/posicoes", json={"latitude": -22.9099, "longitude": -47.0626}, headers=headers)
    assert resposta.status_code == 201, resposta.text

    viagens = client.get("/api/viagens", headers=headers).json()
    viagem = next(v for v in viagens if v["id"] == vid)
    assert viagem["codigo_rastreio"]

    rastreio = client.get(f"/api/viagens/rastrear/{viagem['codigo_rastreio']}").json()
    assert 70 < rastreio["distancia_percorrida_km"] < 110
    assert rastreio["ultima_posicao"] is not None
    assert len(rastreio["trajeto"]) == 2


def test_rastreio_publico_viagem_sem_autenticacao(client, db):
    empresa = criar_empresa_completa(db, "VR2")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    vid = empresa["viagem_id"]

    client.post(f"/api/viagens/{vid}/posicoes", json={"latitude": -23.5505, "longitude": -46.6333}, headers=headers)
    viagens = client.get("/api/viagens", headers=headers).json()
    codigo = next(v for v in viagens if v["id"] == vid)["codigo_rastreio"]

    resposta = client.get(f"/api/viagens/rastrear/{codigo}")
    assert resposta.status_code == 200
    assert resposta.json()["origem"]
    assert resposta.json()["destino"]

    invalido = client.get("/api/viagens/rastrear/NAOEXISTE")
    assert invalido.status_code == 404


def test_viagem_criada_ja_ganha_codigo_de_rastreio(client, db):
    empresa = criar_empresa_completa(db, "VR3")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    nova = client.post(
        "/api/viagens",
        json={
            "rota_id": empresa["rota_id"],
            "onibus_id": empresa["onibus_id"],
            "data_hora_partida": "2026-10-01T06:00:00",
            "preco": 50.0,
        },
        headers=headers,
    )
    assert nova.status_code == 201, nova.text
    assert nova.json()["codigo_rastreio"]


def test_funcionario_de_outra_empresa_nao_registra_posicao(client, db):
    empresa_a = criar_empresa_completa(db, "VR4")
    empresa_b = criar_empresa_completa(db, "VR5")
    headers_b = auth_header(login(client, empresa_b["admin_email"], empresa_b["senha"]))

    resposta = client.post(
        f"/api/viagens/{empresa_a['viagem_id']}/posicoes",
        json={"latitude": -23.5505, "longitude": -46.6333},
        headers=headers_b,
    )
    assert resposta.status_code == 404
