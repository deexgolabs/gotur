from datetime import datetime, timedelta

from app.models.empresa import Empresa
from app.models.evento import AssentoLocal, AssentoSessao, Ingresso, Local, Sessao
from tests.helpers import auth_header, criar_cliente, criar_empresa_completa, login


def _empresa_com_local_e_sessao(client, db, sufixo: str, total_assentos: int = 4):
    empresa = criar_empresa_completa(db, sufixo)
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    resposta_local = client.post(
        "/api/locais",
        json={"nome": f"Teatro {sufixo}", "endereco": "Rua X, 123", "total_assentos": total_assentos},
        headers=headers_admin,
    )
    assert resposta_local.status_code == 201, resposta_local.text
    local = resposta_local.json()

    resposta_sessao = client.post(
        "/api/sessoes",
        json={
            "local_id": local["id"],
            "nome_evento": f"Show {sufixo}",
            "data_hora": (datetime.now() + timedelta(days=5)).isoformat(),
            "preco": 100.0,
        },
        headers=headers_admin,
    )
    assert resposta_sessao.status_code == 201, resposta_sessao.text
    sessao = resposta_sessao.json()

    return {
        "empresa": empresa,
        "headers_admin": headers_admin,
        "local": local,
        "sessao": sessao,
    }


def _assento_livre_id(db, sessao_id: int) -> int:
    return db.query(AssentoSessao).filter(AssentoSessao.sessao_id == sessao_id).first().id


def test_criar_local_com_total_assentos_gera_layout_automatico(client, db):
    cenario = _empresa_com_local_e_sessao(client, db, "EV1", total_assentos=6)
    assentos = db.query(AssentoLocal).filter(AssentoLocal.local_id == cenario["local"]["id"]).all()
    assert len(assentos) == 6


def test_criar_sessao_gera_um_assento_sessao_por_assento_local(client, db):
    cenario = _empresa_com_local_e_sessao(client, db, "EV2", total_assentos=5)
    assentos_sessao = db.query(AssentoSessao).filter(AssentoSessao.sessao_id == cenario["sessao"]["id"]).all()
    assert len(assentos_sessao) == 5
    assert all(a.status.value == "livre" for a in assentos_sessao)


def test_vender_ingresso_apos_hold_previo_do_mesmo_usuario(client, db):
    """Regressão: reservar (hold) o assento antes de comprar — like a tela
    de mapa de assentos sempre faz — precisa funcionar mesmo com o
    hold_expira_em já persistido e recarregado do banco (SQLite descarta o
    tzinfo ao salvar, então comparar contra um datetime timezone-aware
    quebra com TypeError; comprar_ingresso precisa comparar com
    datetime.utcnow(), não datetime.now(timezone.utc))."""
    cenario = _empresa_com_local_e_sessao(client, db, "EV9")
    headers_admin = cenario["headers_admin"]
    assento_id = _assento_livre_id(db, cenario["sessao"]["id"])

    hold = client.post(f"/api/sessoes/{cenario['sessao']['id']}/assentos/{assento_id}/hold", headers=headers_admin)
    assert hold.status_code == 200, hold.text

    resposta = client.post(
        f"/api/sessoes/{cenario['sessao']['id']}/ingressos",
        json={
            "assento_sessao_id": assento_id,
            "cliente_nome": "Pos Hold",
            "cliente_documento": "555.555.555-55",
            "forma_pagamento": "dinheiro",
        },
        headers=headers_admin,
    )
    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["ingresso"]["status"] == "confirmada"


def test_vender_ingresso_com_cartao_aprova_na_hora(client, db):
    cenario = _empresa_com_local_e_sessao(client, db, "EV3")
    cliente = criar_cliente(db, "EV3")
    headers_cliente = auth_header(login(client, cliente["email"], cliente["senha"]))
    assento_id = _assento_livre_id(db, cenario["sessao"]["id"])

    resposta = client.post(
        f"/api/sessoes/{cenario['sessao']['id']}/ingressos",
        json={
            "assento_sessao_id": assento_id,
            "cliente_nome": "Fulano Evento",
            "cliente_documento": "000.000.000-00",
            "forma_pagamento": "cartao",
            "mp_token": "TOK",
            "mp_payment_method_id": "visa",
        },
        headers=headers_cliente,
    )
    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["ingresso"] is not None
    assert corpo["ingresso"]["status"] == "confirmada"
    assert corpo["ingresso"]["preco"] == 100.0
    assert corpo["ingresso"]["codigo"]

    assento = db.get(AssentoSessao, assento_id)
    assert assento.status.value == "vendida"
    assert assento.ingresso_id == corpo["ingresso"]["id"]


def test_comprar_com_pix_fica_pendente_e_confirmar_simulado_libera(client, db):
    cenario = _empresa_com_local_e_sessao(client, db, "EV4")
    cliente = criar_cliente(db, "EV4")
    headers_cliente = auth_header(login(client, cliente["email"], cliente["senha"]))
    assento_id = _assento_livre_id(db, cenario["sessao"]["id"])

    resposta = client.post(
        f"/api/sessoes/{cenario['sessao']['id']}/ingressos",
        json={
            "assento_sessao_id": assento_id,
            "cliente_nome": "Ciclana Evento",
            "cliente_documento": "111.111.111-11",
            "forma_pagamento": "pix",
        },
        headers=headers_cliente,
    )
    assert resposta.status_code == 201, resposta.text
    pedido = resposta.json()["pedido_ingresso"]
    assert pedido["status"] == "pendente"
    assert pedido["pix_copia_cola"]

    assento = db.get(AssentoSessao, assento_id)
    assert assento.status.value == "hold"

    confirmar = client.post(f"/api/pedidos-ingresso/{pedido['id']}/confirmar-simulado", headers=headers_cliente)
    assert confirmar.status_code == 200, confirmar.text
    corpo = confirmar.json()
    assert corpo["ingresso"]["status"] == "confirmada"

    de_novo = client.post(f"/api/pedidos-ingresso/{pedido['id']}/confirmar-simulado", headers=headers_cliente)
    assert de_novo.status_code == 409

    db.expire_all()
    assento_db = db.get(AssentoSessao, assento_id)
    assert assento_db.status.value == "vendida"


def test_cancelar_e_reembolsar_ingresso(client, db):
    cenario = _empresa_com_local_e_sessao(client, db, "EV5")
    cliente = criar_cliente(db, "EV5")
    headers_cliente = auth_header(login(client, cliente["email"], cliente["senha"]))
    assento_id = _assento_livre_id(db, cenario["sessao"]["id"])

    venda = client.post(
        f"/api/sessoes/{cenario['sessao']['id']}/ingressos",
        json={
            "assento_sessao_id": assento_id,
            "cliente_nome": "Beltrano",
            "cliente_documento": "222.222.222-22",
            "forma_pagamento": "cartao",
            "mp_token": "TOK",
            "mp_payment_method_id": "visa",
        },
        headers=headers_cliente,
    ).json()
    ingresso_id = venda["ingresso"]["id"]

    cancelar = client.post(f"/api/ingressos/{ingresso_id}/cancelar", headers=headers_cliente)
    assert cancelar.status_code == 200, cancelar.text
    assert cancelar.json()["status"] == "cancelada"

    assento = db.get(AssentoSessao, assento_id)
    assert assento.status.value == "livre"
    assert assento.ingresso_id is None

    reembolso = client.post(
        f"/api/ingressos/{ingresso_id}/reembolsar",
        json={"motivo": "Show cancelado"},
        headers=cenario["headers_admin"],
    )
    assert reembolso.status_code == 200, reembolso.text
    corpo = reembolso.json()
    assert corpo["valor_reembolsado"] == 100.0

    de_novo = client.post(
        f"/api/ingressos/{ingresso_id}/reembolsar",
        json={"motivo": "De novo"},
        headers=cenario["headers_admin"],
    )
    assert de_novo.status_code == 409


def test_checkin_sucesso_ja_feito_e_codigo_invalido(client, db):
    cenario = _empresa_com_local_e_sessao(client, db, "EV6")
    cliente = criar_cliente(db, "EV6")
    headers_cliente = auth_header(login(client, cliente["email"], cliente["senha"]))
    assento_id = _assento_livre_id(db, cenario["sessao"]["id"])

    venda = client.post(
        f"/api/sessoes/{cenario['sessao']['id']}/ingressos",
        json={
            "assento_sessao_id": assento_id,
            "cliente_nome": "Sicrano",
            "cliente_documento": "333.333.333-33",
            "forma_pagamento": "dinheiro",
        },
        headers=cenario["headers_admin"],
    ).json()
    codigo = venda["ingresso"]["codigo"]

    consulta = client.get(f"/api/checkin-eventos/{codigo}", headers=cenario["headers_admin"])
    assert consulta.status_code == 200, consulta.text
    assert consulta.json()["checkin_em"] is None

    confirmar = client.post(f"/api/checkin-eventos/{codigo}", headers=cenario["headers_admin"])
    assert confirmar.status_code == 200, confirmar.text
    assert confirmar.json()["checkin_em"] is not None

    de_novo = client.post(f"/api/checkin-eventos/{codigo}", headers=cenario["headers_admin"])
    assert de_novo.status_code == 409

    invalido = client.get("/api/checkin-eventos/ZZZZZZ", headers=cenario["headers_admin"])
    assert invalido.status_code == 404


def test_modulo_eventos_desligado_bloqueia_criacao_de_local(client, db):
    empresa = criar_empresa_completa(db, "EV7")
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    empresa_db = db.get(Empresa, empresa["empresa_id"])
    empresa_db.eventos_ativo = False
    db.commit()

    resposta = client.post(
        "/api/locais",
        json={"nome": "Teatro Desligado", "total_assentos": 4},
        headers=headers_admin,
    )
    assert resposta.status_code == 403


def test_isolamento_multi_tenant_entre_empresas(client, db):
    cenario_a = _empresa_com_local_e_sessao(client, db, "EV8A")
    empresa_b = criar_empresa_completa(db, "EV8B")
    headers_b = auth_header(login(client, empresa_b["admin_email"], empresa_b["senha"]))

    locais_b = client.get("/api/locais", headers=headers_b)
    assert locais_b.status_code == 200
    assert locais_b.json() == []

    sessoes_b = client.get("/api/sessoes", headers=headers_b)
    assert sessoes_b.status_code == 200
    assert sessoes_b.json() == []

    editar_local_de_outra_empresa = client.patch(
        f"/api/locais/{cenario_a['local']['id']}",
        json={"nome": "Hack"},
        headers=headers_b,
    )
    assert editar_local_de_outra_empresa.status_code == 404

    ingressos_de_outra_sessao = client.get(
        f"/api/sessoes/{cenario_a['sessao']['id']}/ingressos", headers=headers_b
    )
    assert ingressos_de_outra_sessao.status_code == 404
