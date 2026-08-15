from app.database import SessionLocal
from app.models.empresa import Empresa
from app.models.plano import Plano
from tests.helpers import auth_header, criar_empresa_completa, login


def _empresa_com_plano_sem_premium(db, sufixo: str):
    """Empresa com plano que NÃO inclui frota/motorista/dre/white-label
    (mas mantém passagens/fretamento/frete ligados) — pra testar os
    diferenciais do plano Completo isoladamente."""
    empresa = criar_empresa_completa(db, sufixo)
    plano = Plano(
        nome=f"Essencial {sufixo}",
        preco_mensal=100.0,
        modulo_frota=False,
        modulo_motorista=False,
        modulo_dre=False,
        modulo_white_label=False,
        modulo_nfse=False,
    )
    db.add(plano)
    db.flush()
    db_empresa = db.get(Empresa, empresa["empresa_id"])
    db_empresa.plano_id = plano.id
    db.commit()
    return empresa


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
    client.patch("/api/empresas/minha/modulos", json={"frete_ativo": False}, headers=headers)
    client.patch("/api/empresas/minha/modulos", json={"eventos_ativo": False}, headers=headers)
    client.patch("/api/empresas/minha/modulos", json={"academia_ativo": False}, headers=headers)
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


def test_plano_sem_frota_bloqueia_registrar_documento_de_onibus(client, db):
    empresa = _empresa_com_plano_sem_premium(db, "MOD6")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    bloqueado = client.post(
        f"/api/onibus/{empresa['onibus_id']}/documentos",
        json={"tipo": "crlv", "data_vencimento": "2027-01-01"},
        headers=headers,
    )
    assert bloqueado.status_code == 403


def test_plano_sem_motorista_bloqueia_cadastro_de_motorista(client, db):
    empresa = _empresa_com_plano_sem_premium(db, "MOD7")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    bloqueado = client.post("/api/motoristas", json={"nome": "João"}, headers=headers)
    assert bloqueado.status_code == 403


def test_plano_sem_dre_bloqueia_relatorio(client, db):
    empresa = _empresa_com_plano_sem_premium(db, "MOD8")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    bloqueado = client.get(
        "/api/relatorios/dre",
        params={"inicio": "2026-01-01", "fim": "2026-12-31"},
        headers=headers,
    )
    assert bloqueado.status_code == 403


def test_plano_sem_white_label_bloqueia_configurar_marca(client, db):
    empresa = _empresa_com_plano_sem_premium(db, "MOD9")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    bloqueado = client.patch("/api/empresas/minha/marca", json={"cor_primaria": "#123456"}, headers=headers)
    assert bloqueado.status_code == 403


def test_plano_completo_libera_frota_motorista_dre_white_label(client, db):
    empresa = criar_empresa_completa(db, "MOD10")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    info = client.get("/api/empresas/minha", headers=headers).json()
    assert info["frota_habilitado"] is True
    assert info["motorista_habilitado"] is True
    assert info["dre_habilitado"] is True
    assert info["white_label_habilitado"] is True
    assert info["nfse_habilitado"] is True

    ok_motorista = client.post("/api/motoristas", json={"nome": "Maria"}, headers=headers)
    assert ok_motorista.status_code == 201

    ok_documento = client.post(
        f"/api/onibus/{empresa['onibus_id']}/documentos",
        json={"tipo": "crlv", "data_vencimento": "2027-01-01"},
        headers=headers,
    )
    assert ok_documento.status_code == 201

    ok_dre = client.get(
        "/api/relatorios/dre",
        params={"inicio": "2026-01-01", "fim": "2026-12-31"},
        headers=headers,
    )
    assert ok_dre.status_code == 200
