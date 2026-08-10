from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models.enums import StatusPedidoPagamento, TipoOcupacao
from app.models.ocupacao_poltrona import OcupacaoPoltrona
from app.models.pedido_pagamento import PedidoPagamento
from tests.helpers import auth_header, criar_empresa_completa, login


def _poltrona_livre(client, headers, viagem_id):
    mapa = client.get(f"/api/viagens/{viagem_id}/poltronas", headers=headers).json()
    return next(p for p in mapa if p["status"] == "livre")["poltrona_viagem_id"]


def _comprar(client, headers, viagem_id, poltrona_id, forma_pagamento):
    return client.post(
        f"/api/viagens/{viagem_id}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": "Fulano",
            "cliente_documento": "000.000.000-00",
            "forma_pagamento": forma_pagamento,
        },
        headers=headers,
    )


def test_compra_via_pix_fica_pendente_em_vez_de_vender_na_hora(client, db):
    empresa = criar_empresa_completa(db, "PX1")
    token = login(client, empresa["funcionario_email"], empresa["senha"])
    headers = auth_header(token)
    poltrona_id = _poltrona_livre(client, headers, empresa["viagem_id"])

    resposta = _comprar(client, headers, empresa["viagem_id"], poltrona_id, "pix")
    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["passagem"] is None
    assert corpo["pedido_pagamento"] is not None
    assert corpo["pedido_pagamento"]["status"] == "pendente"
    assert corpo["pedido_pagamento"]["pix_copia_cola"]

    # A poltrona não pode ser vendida a outra pessoa enquanto o Pix está
    # pendente: o assento continua em hold.
    mapa = client.get(f"/api/viagens/{empresa['viagem_id']}/poltronas", headers=headers).json()
    assert next(p for p in mapa if p["poltrona_viagem_id"] == poltrona_id)["status"] == "hold"


def test_compra_via_cartao_continua_aprovando_na_hora(client, db):
    empresa = criar_empresa_completa(db, "PX2")
    token = login(client, empresa["funcionario_email"], empresa["senha"])
    headers = auth_header(token)
    poltrona_id = _poltrona_livre(client, headers, empresa["viagem_id"])

    resposta = _comprar(client, headers, empresa["viagem_id"], poltrona_id, "cartao")
    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["pedido_pagamento"] is None
    assert corpo["passagem"] is not None
    assert corpo["passagem"]["status"] == "confirmada"
    assert corpo["passagem"]["localizador"]


def test_confirmar_pix_simulado_cria_passagem_e_libera_o_pedido(client, db):
    empresa = criar_empresa_completa(db, "PX3")
    token = login(client, empresa["funcionario_email"], empresa["senha"])
    headers = auth_header(token)
    poltrona_id = _poltrona_livre(client, headers, empresa["viagem_id"])

    pedido = _comprar(client, headers, empresa["viagem_id"], poltrona_id, "pix").json()["pedido_pagamento"]

    confirmar = client.post(f"/api/pedidos-pagamento/{pedido['id']}/confirmar-simulado", headers=headers)
    assert confirmar.status_code == 200, confirmar.text
    passagem = confirmar.json()
    assert passagem["status"] == "confirmada"
    assert passagem["localizador"]

    # confirmar de novo deve falhar (já confirmado)
    de_novo = client.post(f"/api/pedidos-pagamento/{pedido['id']}/confirmar-simulado", headers=headers)
    assert de_novo.status_code == 409

    mapa = client.get(f"/api/viagens/{empresa['viagem_id']}/poltronas", headers=headers).json()
    assert next(p for p in mapa if p["poltrona_viagem_id"] == poltrona_id)["status"] == "vendida"


def test_pedido_pix_expirado_nao_pode_ser_confirmado_e_libera_o_assento(client, db):
    empresa = criar_empresa_completa(db, "PX4")
    token = login(client, empresa["funcionario_email"], empresa["senha"])
    headers = auth_header(token)
    poltrona_id = _poltrona_livre(client, headers, empresa["viagem_id"])

    pedido = _comprar(client, headers, empresa["viagem_id"], poltrona_id, "pix").json()["pedido_pagamento"]

    # Simula o tempo passando: expira o pedido e o hold que segurava o assento.
    sessao = SessionLocal()
    passado = datetime.utcnow() - timedelta(minutes=1)
    sessao.query(PedidoPagamento).filter(PedidoPagamento.id == pedido["id"]).update({"expira_em": passado})
    sessao.query(OcupacaoPoltrona).filter(
        OcupacaoPoltrona.poltrona_viagem_id == poltrona_id, OcupacaoPoltrona.tipo == TipoOcupacao.HOLD
    ).update({"expira_em": passado})
    sessao.commit()
    sessao.close()

    consultar = client.get(f"/api/pedidos-pagamento/{pedido['id']}", headers=headers)
    assert consultar.status_code == 200
    assert consultar.json()["status"] == "expirado"

    confirmar = client.post(f"/api/pedidos-pagamento/{pedido['id']}/confirmar-simulado", headers=headers)
    assert confirmar.status_code == 409

    # O assento volta a ficar livre para outra venda.
    mapa = client.get(f"/api/viagens/{empresa['viagem_id']}/poltronas", headers=headers).json()
    assert next(p for p in mapa if p["poltrona_viagem_id"] == poltrona_id)["status"] == "livre"


def test_isolamento_multitenant_no_pedido_de_pagamento(client, db):
    empresa_a = criar_empresa_completa(db, "PX5")
    empresa_b = criar_empresa_completa(db, "PX6")
    token_a = login(client, empresa_a["funcionario_email"], empresa_a["senha"])
    token_b = login(client, empresa_b["funcionario_email"], empresa_b["senha"])
    headers_a = auth_header(token_a)
    headers_b = auth_header(token_b)

    poltrona_id = _poltrona_livre(client, headers_a, empresa_a["viagem_id"])
    pedido = _comprar(client, headers_a, empresa_a["viagem_id"], poltrona_id, "pix").json()["pedido_pagamento"]

    acesso_negado = client.get(f"/api/pedidos-pagamento/{pedido['id']}", headers=headers_b)
    assert acesso_negado.status_code == 403

    confirmar_negado = client.post(f"/api/pedidos-pagamento/{pedido['id']}/confirmar-simulado", headers=headers_b)
    assert confirmar_negado.status_code == 403
