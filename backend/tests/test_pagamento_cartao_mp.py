from app.models.empresa import Empresa
from app.services import pagamento_provider as pp
from tests.helpers import auth_header, criar_empresa_completa, login


def _poltrona_livre(client, headers, viagem_id):
    mapa = client.get(f"/api/viagens/{viagem_id}/poltronas", headers=headers).json()
    return next(p for p in mapa if p["status"] == "livre")["poltrona_viagem_id"]


def test_compra_com_cartao_via_mercadopago_aprova_na_hora(client, db, monkeypatch):
    empresa = criar_empresa_completa(db, "MPC1")
    db_empresa = db.get(Empresa, empresa["empresa_id"])
    db_empresa.mercadopago_access_token = "TOKEN-FAKE-EMPRESA"
    db.commit()

    capturado = {}

    def cobrar_falso(self, *, forma_pagamento, valor, referencia_pedido, dados_cartao=None):
        capturado["dados_cartao"] = dados_cartao
        return pp.ResultadoCobranca(gateway_ref="CARD-PAY-1", status="aprovado")

    monkeypatch.setattr(pp.MercadoPagoProvider, "cobrar", cobrar_falso)

    headers = auth_header(login(client, empresa["funcionario_email"], empresa["senha"]))
    poltrona_id = _poltrona_livre(client, headers, empresa["viagem_id"])
    resposta = client.post(
        f"/api/viagens/{empresa['viagem_id']}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": "Fulano",
            "cliente_documento": "000.000.000-00",
            "forma_pagamento": "cartao",
            "mp_token": "card-token-xyz",
            "mp_payment_method_id": "visa",
            "mp_installments": 3,
            "mp_payer_email": "fulano@teste.com",
        },
        headers=headers,
    )
    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["passagem"]["status"] == "confirmada"

    assert capturado["dados_cartao"].token == "card-token-xyz"
    assert capturado["dados_cartao"].payment_method_id == "visa"
    assert capturado["dados_cartao"].installments == 3
    assert capturado["dados_cartao"].payer_documento == "000.000.000-00"


def test_compra_com_cartao_recusado_nao_vende_passagem(client, db, monkeypatch):
    empresa = criar_empresa_completa(db, "MPC2")
    db_empresa = db.get(Empresa, empresa["empresa_id"])
    db_empresa.mercadopago_access_token = "TOKEN-FAKE-EMPRESA"
    db.commit()

    def cobrar_falso(self, *, forma_pagamento, valor, referencia_pedido, dados_cartao=None):
        return pp.ResultadoCobranca(gateway_ref="CARD-PAY-2", status="recusado")

    monkeypatch.setattr(pp.MercadoPagoProvider, "cobrar", cobrar_falso)

    headers = auth_header(login(client, empresa["funcionario_email"], empresa["senha"]))
    poltrona_id = _poltrona_livre(client, headers, empresa["viagem_id"])
    resposta = client.post(
        f"/api/viagens/{empresa['viagem_id']}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": "Fulano",
            "cliente_documento": "000.000.000-00",
            "forma_pagamento": "cartao",
            "mp_token": "card-token-recusado",
            "mp_payment_method_id": "visa",
        },
        headers=headers,
    )
    assert resposta.status_code == 400

    mapa = client.get(f"/api/viagens/{empresa['viagem_id']}/poltronas", headers=headers).json()
    assert next(p for p in mapa if p["poltrona_viagem_id"] == poltrona_id)["status"] == "livre"
