from tests.helpers import auth_header, criar_empresa_completa, login


def _criar_frete(client, headers, **overrides):
    dados = {
        "remetente_nome": "Loja X",
        "destinatario_nome": "Cliente Y",
        "origem": "São Paulo",
        "destino": "Campos do Jordão",
        "data_hora_coleta": "2026-09-01T06:00:00",
    }
    dados.update(overrides)
    resposta = client.post("/api/fretes", json=dados, headers=headers)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_valor_total_calculado_por_distancia_e_preco_por_km(client, db):
    empresa = criar_empresa_completa(db, "FR1")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    frete = _criar_frete(client, headers, distancia_km=180, valor_por_km=5.5)
    assert frete["valor_total"] == 990.0


def test_valor_total_manual_sobrescreve_calculo(client, db):
    empresa = criar_empresa_completa(db, "FR2")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    frete = _criar_frete(client, headers, distancia_km=100, valor_por_km=5.0, valor_total=333.0)
    assert frete["valor_total"] == 333.0


def test_frete_sem_veiculo_ou_onibus_funciona_para_empresa_sem_frota(client, db):
    """O ponto central do recurso: uma transportadora/caminhoneiro autônomo
    que nunca cadastrou nenhum ônibus tem que conseguir criar frete."""
    empresa = criar_empresa_completa(db, "FR3")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    frete = _criar_frete(client, headers, motorista_nome="João Caminhoneiro", veiculo_descricao="Caminhão placa ABC-1234")
    assert frete["motorista_nome"] == "João Caminhoneiro"
    assert frete["veiculo_descricao"] == "Caminhão placa ABC-1234"
    assert frete["icone_mapa"] == "🚚"


def test_posicoes_gps_calculam_distancia_percorrida(client, db):
    empresa = criar_empresa_completa(db, "FR4")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    frete = _criar_frete(client, headers)
    fid = frete["id"]

    client.post(f"/api/fretes/{fid}/posicoes", json={"latitude": -23.5505, "longitude": -46.6333}, headers=headers)
    resposta = client.post(f"/api/fretes/{fid}/posicoes", json={"latitude": -22.9099, "longitude": -47.0626}, headers=headers)
    assert resposta.status_code == 201

    detalhe = client.get(f"/api/fretes/{fid}", headers=headers).json()
    assert 70 < detalhe["distancia_percorrida_km"] < 110
    assert detalhe["ultima_posicao"] is not None


def test_rastreio_publico_sem_autenticacao(client, db):
    empresa = criar_empresa_completa(db, "FR5")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    frete = _criar_frete(client, headers)
    codigo = frete["codigo_rastreio"]

    resposta = client.get(f"/api/fretes/rastrear/{codigo}")
    assert resposta.status_code == 200
    assert resposta.json()["destinatario_nome"] == "Cliente Y"

    invalido = client.get("/api/fretes/rastrear/NAOEXISTE")
    assert invalido.status_code == 404


def test_mudar_status_e_isolamento_multitenant(client, db):
    empresa_a = criar_empresa_completa(db, "FR6")
    empresa_b = criar_empresa_completa(db, "FR7")
    token_a = login(client, empresa_a["admin_email"], empresa_a["senha"])
    token_b = login(client, empresa_b["admin_email"], empresa_b["senha"])

    frete = _criar_frete(client, auth_header(token_a))

    status_resp = client.patch(
        f"/api/fretes/{frete['id']}/status", json={"status": "em_transito"}, headers=auth_header(token_a)
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "em_transito"

    invasao = client.get(f"/api/fretes/{frete['id']}", headers=auth_header(token_b))
    assert invasao.status_code == 404


def test_solicitar_frete_pela_loja_publica_e_bloqueado_se_modulo_desligado(client, db):
    empresa = criar_empresa_completa(db, "FR8")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)
    slug = client.get("/api/empresas/minha", headers=headers).json()["slug"]

    resposta = client.post(
        f"/api/fretes/loja/{slug}/solicitar",
        json={
            "remetente_nome": "Fulano",
            "remetente_contato": "fulano@teste.com",
            "destinatario_nome": "Beltrano",
            "origem": "A",
            "destino": "B",
            "data_hora_coleta": "2026-09-01T06:00:00",
        },
    )
    assert resposta.status_code == 201, resposta.text

    client.patch("/api/empresas/minha/modulos", json={"frete_ativo": False}, headers=headers)
    bloqueado = client.post(
        f"/api/fretes/loja/{slug}/solicitar",
        json={
            "remetente_nome": "Fulano",
            "remetente_contato": "fulano@teste.com",
            "destinatario_nome": "Beltrano",
            "origem": "A",
            "destino": "B",
            "data_hora_coleta": "2026-09-01T06:00:00",
        },
    )
    assert bloqueado.status_code == 404


def test_emitir_nfse_frete_exige_status_entregue(client, db):
    empresa = criar_empresa_completa(db, "FR9")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    frete = _criar_frete(client, headers)
    ainda_solicitado = client.post(f"/api/fretes/{frete['id']}/nfse", headers=headers)
    assert ainda_solicitado.status_code == 409

    client.patch(f"/api/fretes/{frete['id']}/status", json={"status": "confirmado"}, headers=headers)
    client.patch(f"/api/fretes/{frete['id']}/status", json={"status": "em_transito"}, headers=headers)
    client.patch(f"/api/fretes/{frete['id']}/status", json={"status": "entregue"}, headers=headers)

    resposta = client.post(f"/api/fretes/{frete['id']}/nfse", headers=headers)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "simulada"
