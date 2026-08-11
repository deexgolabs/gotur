from app.models.enums import TipoRastreioPush
from app.models.push_inscricao import PushInscricao
from tests.helpers import auth_header, criar_empresa_completa, login


def _criar_fretamento(client, headers, **overrides):
    dados = {
        "cliente_nome": "Cliente Teste",
        "origem": "São Paulo",
        "destino": "Campinas",
        "data_hora_saida": "2026-09-01T06:00:00",
    }
    dados.update(overrides)
    resposta = client.post("/api/fretamentos", json=dados, headers=headers)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


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


def _payload_inscricao(sufixo: str = "1"):
    return {
        "endpoint": f"https://push.exemplo.com/inscricao-{sufixo}",
        "keys": {"p256dh": "chave-p256dh-fake", "auth": "chave-auth-fake"},
    }


def test_chave_publica_vem_none_sem_vapid_configurado(client):
    resposta = client.get("/api/push/chave-publica")
    assert resposta.status_code == 200
    assert resposta.json()["chave_publica"] is None


def test_inscrever_push_fretamento_sem_autenticacao(client, db):
    empresa = criar_empresa_completa(db, "PUSH1")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    fretamento = _criar_fretamento(client, headers)
    codigo = fretamento["codigo_rastreio"]

    resposta = client.post(f"/api/fretamentos/rastrear/{codigo}/push", json=_payload_inscricao())
    assert resposta.status_code == 204

    inscricoes = db.query(PushInscricao).filter(PushInscricao.tipo == TipoRastreioPush.FRETAMENTO).all()
    assert len(inscricoes) == 1
    assert inscricoes[0].objeto_id == fretamento["id"]


def test_inscrever_push_e_idempotente_pro_mesmo_endpoint(client, db):
    empresa = criar_empresa_completa(db, "PUSH2")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    fretamento = _criar_fretamento(client, headers)
    codigo = fretamento["codigo_rastreio"]

    client.post(f"/api/fretamentos/rastrear/{codigo}/push", json=_payload_inscricao("mesmo"))
    client.post(f"/api/fretamentos/rastrear/{codigo}/push", json=_payload_inscricao("mesmo"))

    inscricoes = db.query(PushInscricao).filter(PushInscricao.tipo == TipoRastreioPush.FRETAMENTO).all()
    assert len(inscricoes) == 1


def test_inscrever_push_codigo_invalido_da_404(client):
    resposta = client.post("/api/fretamentos/rastrear/NAOEXISTE/push", json=_payload_inscricao())
    assert resposta.status_code == 404


def test_inscrever_push_frete_sem_autenticacao(client, db):
    empresa = criar_empresa_completa(db, "PUSH3")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    frete = _criar_frete(client, headers)
    codigo = frete["codigo_rastreio"]

    resposta = client.post(f"/api/fretes/rastrear/{codigo}/push", json=_payload_inscricao())
    assert resposta.status_code == 204

    inscricoes = db.query(PushInscricao).filter(PushInscricao.tipo == TipoRastreioPush.FRETE).all()
    assert len(inscricoes) == 1
    assert inscricoes[0].objeto_id == frete["id"]


def test_mudar_status_com_inscricao_push_nao_quebra_sem_vapid_configurado(client, db):
    """Sem GOTUR_VAPID_PUBLIC_KEY/PRIVATE_KEY configurados (padrão de teste),
    o envio deve ser só logado (no-op) — a mudança de status não pode falhar
    nem apagar a inscrição."""
    empresa = criar_empresa_completa(db, "PUSH4")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    frete = _criar_frete(client, headers)
    codigo = frete["codigo_rastreio"]

    client.post(f"/api/fretes/rastrear/{codigo}/push", json=_payload_inscricao())

    resposta = client.patch(f"/api/fretes/{frete['id']}/status", json={"status": "em_transito"}, headers=headers)
    assert resposta.status_code == 200

    inscricoes = db.query(PushInscricao).filter(PushInscricao.tipo == TipoRastreioPush.FRETE).all()
    assert len(inscricoes) == 1
