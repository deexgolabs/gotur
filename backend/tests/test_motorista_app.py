from app.models.viagem import Viagem
from tests.helpers import auth_header, criar_empresa_completa, login


def _criar_motorista(client, headers, nome="Carlos Motorista"):
    resposta = client.post("/api/motoristas", json={"nome": nome}, headers=headers)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _criar_acesso(client, headers, motorista_id, email, senha="senha123"):
    resposta = client.post(f"/api/motoristas/{motorista_id}/acesso", json={"email": email, "senha": senha}, headers=headers)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_criar_acesso_motorista_e_logar(client, db):
    empresa = criar_empresa_completa(db, "MA1")
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    motorista = _criar_motorista(client, headers_admin)

    corpo = _criar_acesso(client, headers_admin, motorista["id"], "motorista.ma1@teste.com")
    assert corpo["tem_acesso"] is True

    login_resp = client.post("/api/auth/login", json={"email": "motorista.ma1@teste.com", "senha": "senha123"})
    assert login_resp.status_code == 200
    assert login_resp.json()["role"] == "motorista"


def test_motorista_ve_apenas_a_propria_agenda(client, db):
    empresa = criar_empresa_completa(db, "MA2")
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    motorista_a = _criar_motorista(client, headers_admin, "Motorista A")
    motorista_b = _criar_motorista(client, headers_admin, "Motorista B")
    _criar_acesso(client, headers_admin, motorista_a["id"], "motorista.a@teste.com")

    db_viagem = db.get(Viagem, empresa["viagem_id"])
    db_viagem.motorista_id = motorista_a["id"]
    db.commit()

    headers_motorista = auth_header(login(client, "motorista.a@teste.com", "senha123"))
    agenda = client.get("/api/motoristas/minha/viagens", headers=headers_motorista)
    assert agenda.status_code == 200
    corpo = agenda.json()
    assert len(corpo) == 1
    assert corpo[0]["tipo"] == "viagem"
    assert corpo[0]["id"] == empresa["viagem_id"]

    # Motorista B não tem nada atribuído.
    _criar_acesso(client, headers_admin, motorista_b["id"], "motorista.b@teste.com")
    headers_motorista_b = auth_header(login(client, "motorista.b@teste.com", "senha123"))
    agenda_b = client.get("/api/motoristas/minha/viagens", headers=headers_motorista_b)
    assert agenda_b.json() == []


def test_motorista_inicia_e_encerra_jornada_do_proprio_trajeto(client, db):
    empresa = criar_empresa_completa(db, "MA3")
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    motorista = _criar_motorista(client, headers_admin, "Motorista Jornada")
    _criar_acesso(client, headers_admin, motorista["id"], "motorista.jornada@teste.com")

    db_viagem = db.get(Viagem, empresa["viagem_id"])
    db_viagem.motorista_id = motorista["id"]
    db.commit()

    headers_motorista = auth_header(login(client, "motorista.jornada@teste.com", "senha123"))

    # Manda um nome diferente de propósito — o servidor deve ignorar e usar o próprio.
    iniciar = client.post(
        "/api/jornadas",
        json={"motorista_nome": "Nome Forjado", "tipo_viagem": "viagem", "referencia_id": empresa["viagem_id"]},
        headers=headers_motorista,
    )
    assert iniciar.status_code == 201, iniciar.text
    jornada = iniciar.json()
    assert jornada["motorista_nome"] == "Motorista Jornada"

    encerrar = client.patch(f"/api/jornadas/{jornada['id']}/encerrar", headers=headers_motorista)
    assert encerrar.status_code == 200
    assert encerrar.json()["fim"] is not None


def test_motorista_nao_registra_jornada_de_trajeto_alheio(client, db):
    empresa = criar_empresa_completa(db, "MA4")
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    motorista = _criar_motorista(client, headers_admin, "Motorista Sem Vinculo")
    _criar_acesso(client, headers_admin, motorista["id"], "motorista.semvinculo@teste.com")
    # Não atribui a viagem a esse motorista.

    headers_motorista = auth_header(login(client, "motorista.semvinculo@teste.com", "senha123"))
    resposta = client.post(
        "/api/jornadas",
        json={"motorista_nome": "Motorista Sem Vinculo", "tipo_viagem": "viagem", "referencia_id": empresa["viagem_id"]},
        headers=headers_motorista,
    )
    assert resposta.status_code == 403


def test_motorista_registra_checklist_do_proprio_trajeto(client, db):
    empresa = criar_empresa_completa(db, "MA5")
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    motorista = _criar_motorista(client, headers_admin, "Motorista Checklist")
    _criar_acesso(client, headers_admin, motorista["id"], "motorista.checklist@teste.com")

    db_viagem = db.get(Viagem, empresa["viagem_id"])
    db_viagem.motorista_id = motorista["id"]
    db.commit()

    headers_motorista = auth_header(login(client, "motorista.checklist@teste.com", "senha123"))
    resposta = client.post(
        "/api/checklists",
        json={
            "motorista_nome": "Ignorado",
            "tipo_viagem": "viagem",
            "referencia_id": empresa["viagem_id"],
            "pneus_ok": True,
            "oleo_ok": True,
            "combustivel_ok": True,
        },
        headers=headers_motorista,
    )
    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["motorista_nome"] == "Motorista Checklist"


def test_funcionario_continua_registrando_jornada_de_qualquer_motorista(client, db):
    """Garante que a permissão nova (MOTORISTA) não quebrou o fluxo
    existente do admin/funcionário controlando jornada de texto livre."""
    empresa = criar_empresa_completa(db, "MA6")
    headers_func = auth_header(login(client, empresa["funcionario_email"], empresa["senha"]))

    resposta = client.post(
        "/api/jornadas",
        json={"motorista_nome": "Motorista Qualquer", "tipo_viagem": "viagem", "referencia_id": empresa["viagem_id"]},
        headers=headers_func,
    )
    assert resposta.status_code == 201
    assert resposta.json()["motorista_nome"] == "Motorista Qualquer"
