from app.database import SessionLocal
from app.models.empresa import Empresa
from tests.helpers import auth_header, criar_empresa_completa, login


def _criar_fretamento(client, headers, **overrides):
    dados = {
        "cliente_nome": "Excursão Escola X",
        "origem": "São Paulo",
        "destino": "Campos do Jordão",
        "data_hora_saida": "2026-09-01T06:00:00",
    }
    dados.update(overrides)
    resposta = client.post("/api/fretamentos", json=dados, headers=headers)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_valor_total_calculado_por_distancia_e_preco_por_km(client, db):
    empresa = criar_empresa_completa(db, "F1")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    fretamento = _criar_fretamento(client, headers, distancia_km=180, valor_por_km=5.5)
    assert fretamento["valor_total"] == 990.0


def test_usa_preco_km_padrao_da_empresa_quando_nao_informado(client, db):
    empresa = criar_empresa_completa(db, "F2")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    configurar = client.patch("/api/empresas/minha/fretamento", json={"preco_km_fretamento": 4.0}, headers=headers)
    assert configurar.status_code == 200

    fretamento = _criar_fretamento(client, headers, distancia_km=100)
    assert fretamento["valor_por_km"] == 4.0
    assert fretamento["valor_total"] == 400.0


def test_valor_total_manual_sobrescreve_calculo(client, db):
    empresa = criar_empresa_completa(db, "F3")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    fretamento = _criar_fretamento(client, headers, distancia_km=100, valor_por_km=5.0, valor_total=333.0)
    assert fretamento["valor_total"] == 333.0


def test_posicoes_gps_calculam_distancia_percorrida(client, db):
    empresa = criar_empresa_completa(db, "F4")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    fretamento = _criar_fretamento(client, headers)
    fid = fretamento["id"]

    # São Paulo -> Campinas (~90km em linha reta) em dois pontos.
    client.post(f"/api/fretamentos/{fid}/posicoes", json={"latitude": -23.5505, "longitude": -46.6333}, headers=headers)
    resposta = client.post(f"/api/fretamentos/{fid}/posicoes", json={"latitude": -22.9099, "longitude": -47.0626}, headers=headers)
    assert resposta.status_code == 201

    detalhe = client.get(f"/api/fretamentos/{fid}", headers=headers).json()
    assert 70 < detalhe["distancia_percorrida_km"] < 110
    assert detalhe["ultima_posicao"] is not None


def test_rastreio_publico_sem_autenticacao(client, db):
    empresa = criar_empresa_completa(db, "F5")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    fretamento = _criar_fretamento(client, headers)
    codigo = fretamento["codigo_rastreio"]

    resposta = client.get(f"/api/fretamentos/rastrear/{codigo}")
    assert resposta.status_code == 200
    assert resposta.json()["cliente_nome"] == "Excursão Escola X"

    invalido = client.get("/api/fretamentos/rastrear/NAOEXISTE")
    assert invalido.status_code == 404


def test_mudar_status_e_isolamento_multitenant(client, db):
    empresa_a = criar_empresa_completa(db, "F6")
    empresa_b = criar_empresa_completa(db, "F7")
    token_a = login(client, empresa_a["admin_email"], empresa_a["senha"])
    token_b = login(client, empresa_b["admin_email"], empresa_b["senha"])

    fretamento = _criar_fretamento(client, auth_header(token_a))

    status_resp = client.patch(
        f"/api/fretamentos/{fretamento['id']}/status", json={"status": "confirmado"}, headers=auth_header(token_a)
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "confirmado"

    # Empresa B não pode ver/alterar o fretamento da empresa A.
    invasao = client.get(f"/api/fretamentos/{fretamento['id']}", headers=auth_header(token_b))
    assert invasao.status_code == 404


def test_contrato_pdf_exige_fretamento_confirmado(client, db):
    empresa = criar_empresa_completa(db, "F8")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    fretamento = _criar_fretamento(client, headers)
    ainda_orcamento = client.get(f"/api/fretamentos/{fretamento['id']}/contrato.pdf", headers=headers)
    assert ainda_orcamento.status_code == 409

    client.patch(f"/api/fretamentos/{fretamento['id']}/status", json={"status": "confirmado"}, headers=headers)
    resposta = client.get(f"/api/fretamentos/{fretamento['id']}/contrato.pdf", headers=headers)
    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "application/pdf"
    assert resposta.content.startswith(b"%PDF")


def test_emitir_nfse_fretamento_exige_status_concluido(client, db):
    empresa = criar_empresa_completa(db, "F9")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    fretamento = _criar_fretamento(client, headers)
    ainda_orcamento = client.post(f"/api/fretamentos/{fretamento['id']}/nfse", headers=headers)
    assert ainda_orcamento.status_code == 409

    client.patch(f"/api/fretamentos/{fretamento['id']}/status", json={"status": "confirmado"}, headers=headers)
    client.patch(f"/api/fretamentos/{fretamento['id']}/status", json={"status": "em_andamento"}, headers=headers)
    client.patch(f"/api/fretamentos/{fretamento['id']}/status", json={"status": "concluido"}, headers=headers)

    resposta = client.post(f"/api/fretamentos/{fretamento['id']}/nfse", headers=headers)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "simulada"
