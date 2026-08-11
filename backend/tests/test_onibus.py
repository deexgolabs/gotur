from datetime import date, timedelta

from tests.helpers import auth_header, criar_empresa_completa, login


def test_editar_quilometragem_do_onibus(client, db):
    empresa = criar_empresa_completa(db, "ONI1")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    resposta = client.patch(f"/api/onibus/{empresa['onibus_id']}", json={"quilometragem_atual": 12345.5}, headers=headers)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["quilometragem_atual"] == 12345.5


def test_criar_listar_editar_e_remover_documento_de_onibus(client, db):
    empresa = criar_empresa_completa(db, "ONI2")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    onibus_id = empresa["onibus_id"]

    vencimento = (date.today() + timedelta(days=10)).isoformat()
    criado = client.post(
        f"/api/onibus/{onibus_id}/documentos",
        json={"tipo": "crlv", "descricao": "CRLV 2026", "data_vencimento": vencimento},
        headers=headers,
    )
    assert criado.status_code == 201, criado.text
    documento = criado.json()
    assert documento["tipo"] == "crlv"
    assert documento["data_vencimento"] == vencimento

    lista = client.get("/api/onibus", headers=headers).json()
    onibus = next(o for o in lista if o["id"] == onibus_id)
    assert len(onibus["documentos"]) == 1
    assert onibus["documentos"][0]["id"] == documento["id"]

    nova_data = (date.today() + timedelta(days=365)).isoformat()
    editado = client.patch(
        f"/api/onibus/{onibus_id}/documentos/{documento['id']}",
        json={"data_vencimento": nova_data},
        headers=headers,
    )
    assert editado.status_code == 200
    assert editado.json()["data_vencimento"] == nova_data

    removido = client.delete(f"/api/onibus/{onibus_id}/documentos/{documento['id']}", headers=headers)
    assert removido.status_code == 204

    lista_final = client.get("/api/onibus", headers=headers).json()
    onibus_final = next(o for o in lista_final if o["id"] == onibus_id)
    assert onibus_final["documentos"] == []


def test_documento_de_onibus_de_outra_empresa_e_rejeitado(client, db):
    empresa_a = criar_empresa_completa(db, "ONI3")
    empresa_b = criar_empresa_completa(db, "ONI4")
    headers_a = auth_header(login(client, empresa_a["admin_email"], empresa_a["senha"]))

    resposta = client.post(
        f"/api/onibus/{empresa_b['onibus_id']}/documentos",
        json={"tipo": "seguro", "data_vencimento": date.today().isoformat()},
        headers=headers_a,
    )
    assert resposta.status_code == 404


def test_funcionario_nao_cria_documento_de_onibus(client, db):
    empresa = criar_empresa_completa(db, "ONI5")
    headers = auth_header(login(client, empresa["funcionario_email"], empresa["senha"]))

    resposta = client.post(
        f"/api/onibus/{empresa['onibus_id']}/documentos",
        json={"tipo": "revisao", "data_vencimento": date.today().isoformat()},
        headers=headers,
    )
    assert resposta.status_code == 403
