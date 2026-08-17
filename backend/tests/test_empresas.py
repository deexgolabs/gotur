from tests.helpers import auth_header, criar_empresa_completa, criar_super_admin, login


def test_excluir_empresa_exige_estar_desativada_primeiro(client, db):
    empresa = criar_empresa_completa(db, "EMP1")
    super_admin = criar_super_admin(db, "EMP1")
    headers_super = auth_header(login(client, super_admin["email"], super_admin["senha"]))

    resposta = client.patch(f"/api/empresas/{empresa['empresa_id']}/excluir", headers=headers_super)
    assert resposta.status_code == 400, resposta.text


def test_excluir_empresa_desativada_some_da_listagem(client, db):
    empresa = criar_empresa_completa(db, "EMP2")
    super_admin = criar_super_admin(db, "EMP2")
    headers_super = auth_header(login(client, super_admin["email"], super_admin["senha"]))

    desativar = client.patch(f"/api/empresas/{empresa['empresa_id']}/desativar", headers=headers_super)
    assert desativar.status_code == 200, desativar.text

    excluir = client.patch(f"/api/empresas/{empresa['empresa_id']}/excluir", headers=headers_super)
    assert excluir.status_code == 200, excluir.text
    assert excluir.json()["excluida_em"] is not None

    lista = client.get("/api/empresas", headers=headers_super).json()
    assert all(e["id"] != empresa["empresa_id"] for e in lista)


def test_excluir_empresa_ja_excluida_da_conflito(client, db):
    empresa = criar_empresa_completa(db, "EMP3")
    super_admin = criar_super_admin(db, "EMP3")
    headers_super = auth_header(login(client, super_admin["email"], super_admin["senha"]))

    client.patch(f"/api/empresas/{empresa['empresa_id']}/desativar", headers=headers_super)
    primeira = client.patch(f"/api/empresas/{empresa['empresa_id']}/excluir", headers=headers_super)
    assert primeira.status_code == 200, primeira.text

    segunda = client.patch(f"/api/empresas/{empresa['empresa_id']}/excluir", headers=headers_super)
    assert segunda.status_code == 409


def test_excluir_empresa_exige_super_admin(client, db):
    empresa = criar_empresa_completa(db, "EMP4")
    token_admin = login(client, empresa["admin_email"], empresa["senha"])
    headers_admin = auth_header(token_admin)

    resposta = client.patch(f"/api/empresas/{empresa['empresa_id']}/excluir", headers=headers_admin)
    assert resposta.status_code == 403
