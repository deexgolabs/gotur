from tests.helpers import auth_header, criar_empresa_completa, login


def test_por_padrao_ambos_modulos_habilitados(client, db):
    empresa = criar_empresa_completa(db, "MOD1")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    resposta = client.get("/api/empresas/minha", headers=headers)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["fretamento_habilitado"] is True
    assert corpo["passagens_habilitado"] is True


def test_desligar_fretamento_bloqueia_criacao_e_solicitacao_publica(client, db):
    empresa = criar_empresa_completa(db, "MOD2")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    desligar = client.patch("/api/empresas/minha/modulos", json={"fretamento_ativo": False}, headers=headers)
    assert desligar.status_code == 200
    assert desligar.json()["fretamento_habilitado"] is False

    bloqueado = client.post(
        "/api/fretamentos",
        json={"cliente_nome": "X", "origem": "A", "destino": "B", "data_hora_saida": "2026-10-01T06:00:00"},
        headers=headers,
    )
    assert bloqueado.status_code == 403

    slug = client.get("/api/empresas/minha", headers=headers).json()["slug"]
    solicitacao_publica = client.post(
        f"/api/fretamentos/loja/{slug}/solicitar",
        json={"cliente_nome": "X", "cliente_contato": "y@teste.com", "origem": "A", "destino": "B", "data_hora_saida": "2026-10-01T06:00:00"},
    )
    assert solicitacao_publica.status_code == 404

    loja_info = client.get(f"/api/empresas/loja/{slug}")
    assert loja_info.json()["fretamento_habilitado"] is False


def test_desligar_passagens_bloqueia_criacao_de_viagem(client, db):
    empresa = criar_empresa_completa(db, "MOD3")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    client.patch("/api/empresas/minha/modulos", json={"passagens_ativo": False}, headers=headers)

    bloqueado = client.post(
        "/api/viagens",
        json={"rota_id": empresa["rota_id"], "onibus_id": empresa["onibus_id"], "data_hora_partida": "2026-10-01T06:00:00", "preco": 50.0},
        headers=headers,
    )
    assert bloqueado.status_code == 403


def test_nao_pode_desligar_os_dois_modulos_ao_mesmo_tempo(client, db):
    empresa = criar_empresa_completa(db, "MOD4")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    client.patch("/api/empresas/minha/modulos", json={"fretamento_ativo": False}, headers=headers)
    resposta = client.patch("/api/empresas/minha/modulos", json={"passagens_ativo": False}, headers=headers)
    assert resposta.status_code == 400


def test_plano_sem_modulo_de_fretamento_impede_empresa_de_ligar(client, db):
    empresa = criar_empresa_completa(db, "MOD5")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    from app.database import SessionLocal
    from app.models.plano import Plano

    sessao = SessionLocal()
    plano = Plano(nome="Sem Fretamento", preco_mensal=10.0, modulo_fretamento=False, modulo_passagens=True)
    sessao.add(plano)
    sessao.commit()
    sessao.refresh(plano)
    from app.models.empresa import Empresa

    emp = sessao.query(Empresa).filter(Empresa.id == empresa["empresa_id"]).first()
    emp.plano_id = plano.id
    sessao.commit()
    sessao.close()

    info = client.get("/api/empresas/minha", headers=headers).json()
    assert info["fretamento_habilitado"] is False  # mesmo com fretamento_ativo=True, o plano não permite

    bloqueado = client.post(
        "/api/fretamentos",
        json={"cliente_nome": "X", "origem": "A", "destino": "B", "data_hora_saida": "2026-10-01T06:00:00"},
        headers=headers,
    )
    assert bloqueado.status_code == 403
