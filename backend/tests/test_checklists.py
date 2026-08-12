from tests.helpers import auth_header, criar_empresa_completa, login


def test_registrar_e_listar_checklist_da_viagem(client, db):
    empresa = criar_empresa_completa(db, "CHK1")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    criado = client.post(
        "/api/checklists",
        json={
            "motorista_nome": "Carlos Motorista",
            "tipo_viagem": "viagem",
            "referencia_id": empresa["viagem_id"],
            "pneus_ok": True,
            "oleo_ok": True,
            "combustivel_ok": False,
            "observacoes": "Combustível baixo, abastecer antes de sair",
        },
        headers=headers,
    )
    assert criado.status_code == 201, criado.text
    checklist = criado.json()
    assert checklist["pneus_ok"] is True
    assert checklist["combustivel_ok"] is False

    lista = client.get(
        f"/api/checklists?tipo_viagem=viagem&referencia_id={empresa['viagem_id']}",
        headers=headers,
    )
    assert lista.status_code == 200
    corpo = lista.json()
    assert len(corpo) == 1
    assert corpo[0]["id"] == checklist["id"]


def test_isolamento_multitenant_checklist(client, db):
    empresa_a = criar_empresa_completa(db, "CHK2")
    empresa_b = criar_empresa_completa(db, "CHK3")
    headers_a = auth_header(login(client, empresa_a["admin_email"], empresa_a["senha"]))
    headers_b = auth_header(login(client, empresa_b["admin_email"], empresa_b["senha"]))

    client.post(
        "/api/checklists",
        json={"motorista_nome": "Motorista A", "tipo_viagem": "viagem", "referencia_id": empresa_a["viagem_id"], "pneus_ok": True},
        headers=headers_a,
    )

    lista_b = client.get(
        f"/api/checklists?tipo_viagem=viagem&referencia_id={empresa_a['viagem_id']}",
        headers=headers_b,
    )
    assert lista_b.status_code == 200
    assert lista_b.json() == []


def test_funcionario_pode_registrar_checklist(client, db):
    empresa = criar_empresa_completa(db, "CHK4")
    headers = auth_header(login(client, empresa["funcionario_email"], empresa["senha"]))

    resposta = client.post(
        "/api/checklists",
        json={"motorista_nome": "Motorista X", "tipo_viagem": "viagem", "referencia_id": empresa["viagem_id"], "oleo_ok": True},
        headers=headers,
    )
    assert resposta.status_code == 201
