from datetime import datetime, timedelta, timezone

from app.models.empresa import Empresa
from app.models.enums import StatusFatura, StatusPedidoPagamento
from app.models.fatura_empresa import FaturaEmpresa
from app.models.pedido_pagamento import PedidoPagamento
from app.services import pagamento_provider as pp
from tests.helpers import auth_header, criar_empresa_completa, criar_super_admin, login


def _poltrona_livre(client, headers, viagem_id):
    mapa = client.get(f"/api/viagens/{viagem_id}/poltronas", headers=headers).json()
    return next(p for p in mapa if p["status"] == "livre")["poltrona_viagem_id"]


def test_webhook_confirma_pedido_pendente_quando_pagamento_aprovado(client, db, monkeypatch):
    empresa = criar_empresa_completa(db, "WH1")
    db_empresa = db.get(Empresa, empresa["empresa_id"])
    db_empresa.mercadopago_access_token = "TOKEN-FAKE-EMPRESA"
    db.commit()

    def cobrar_falso(self, *, forma_pagamento, valor, referencia_pedido, dados_cartao=None, dados_boleto=None):
        return pp.ResultadoCobranca(
            gateway_ref="PAY-WEBHOOK-1",
            status="pendente",
            pix_copia_cola="00020FAKE",
            pix_expira_em=datetime.now(timezone.utc) + timedelta(minutes=15),
        )

    monkeypatch.setattr(pp.MercadoPagoProvider, "cobrar", cobrar_falso)

    headers = auth_header(login(client, empresa["funcionario_email"], empresa["senha"]))
    poltrona_id = _poltrona_livre(client, headers, empresa["viagem_id"])
    compra = client.post(
        f"/api/viagens/{empresa['viagem_id']}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": "Fulano",
            "cliente_documento": "000.000.000-00",
            "forma_pagamento": "pix",
        },
        headers=headers,
    )
    assert compra.status_code == 201, compra.text
    pedido = compra.json()["pedido_pagamento"]
    assert pedido["status"] == "pendente"

    monkeypatch.setattr(pp.MercadoPagoProvider, "consultar_status", lambda self, ref: "approved")

    resposta = client.post("/api/webhooks/mercadopago", json={"type": "payment", "data": {"id": "PAY-WEBHOOK-1"}})
    assert resposta.status_code == 200

    pedido_db = db.get(PedidoPagamento, pedido["id"])
    db.refresh(pedido_db)
    assert pedido_db.status == StatusPedidoPagamento.CONFIRMADO
    assert pedido_db.passagem_id is not None


def test_webhook_nao_confirma_quando_mercado_pago_ainda_nao_aprovou(client, db, monkeypatch):
    empresa = criar_empresa_completa(db, "WH2")
    db_empresa = db.get(Empresa, empresa["empresa_id"])
    db_empresa.mercadopago_access_token = "TOKEN-FAKE-EMPRESA"
    db.commit()

    def cobrar_falso(self, *, forma_pagamento, valor, referencia_pedido, dados_cartao=None, dados_boleto=None):
        return pp.ResultadoCobranca(
            gateway_ref="PAY-WEBHOOK-2",
            status="pendente",
            pix_copia_cola="00020FAKE",
            pix_expira_em=datetime.now(timezone.utc) + timedelta(minutes=15),
        )

    monkeypatch.setattr(pp.MercadoPagoProvider, "cobrar", cobrar_falso)

    headers = auth_header(login(client, empresa["funcionario_email"], empresa["senha"]))
    poltrona_id = _poltrona_livre(client, headers, empresa["viagem_id"])
    compra = client.post(
        f"/api/viagens/{empresa['viagem_id']}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": "Fulano",
            "cliente_documento": "000.000.000-00",
            "forma_pagamento": "pix",
        },
        headers=headers,
    )
    pedido_id = compra.json()["pedido_pagamento"]["id"]

    monkeypatch.setattr(pp.MercadoPagoProvider, "consultar_status", lambda self, ref: "pending")

    resposta = client.post("/api/webhooks/mercadopago", json={"type": "payment", "data": {"id": "PAY-WEBHOOK-2"}})
    assert resposta.status_code == 200

    pedido_db = db.get(PedidoPagamento, pedido_id)
    assert pedido_db.status == StatusPedidoPagamento.PENDENTE


def test_webhook_confirma_fatura_pendente_quando_aprovado(client, db, monkeypatch):
    super_admin = criar_super_admin(db, "WH3")
    headers_super = auth_header(login(client, super_admin["email"], super_admin["senha"]))
    plano = client.post(
        "/api/planos",
        json={"nome": "Basico", "preco_mensal": 99.9, "max_onibus": 1, "max_funcionarios": 2, "max_viagens_mes": 1},
        headers=headers_super,
    ).json()

    empresa = criar_empresa_completa(db, "WH3")
    db_empresa = db.get(Empresa, empresa["empresa_id"])
    db_empresa.plano_id = plano["id"]
    db.commit()

    from app.models.configuracao_plataforma import ConfiguracaoPlataforma

    plataforma = db.query(ConfiguracaoPlataforma).first()
    if not plataforma:
        plataforma = ConfiguracaoPlataforma()
        db.add(plataforma)
        db.commit()
    plataforma.mercadopago_access_token = "TOKEN-FAKE-PLATAFORMA"
    db.commit()

    fatura_id = client.post(f"/api/empresas/{empresa['empresa_id']}/faturas", headers=headers_super).json()["id"]

    def cobrar_falso(self, *, forma_pagamento, valor, referencia_pedido, dados_cartao=None, dados_boleto=None):
        return pp.ResultadoCobranca(
            gateway_ref="PAY-WEBHOOK-FATURA-1",
            status="pendente",
            pix_copia_cola="00020FAKE",
            pix_expira_em=datetime.now(timezone.utc) + timedelta(minutes=15),
        )

    monkeypatch.setattr(pp.MercadoPagoProvider, "cobrar", cobrar_falso)

    headers_empresa = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    pagar = client.post(f"/api/faturas/{fatura_id}/pagar", headers=headers_empresa)
    assert pagar.status_code == 200
    assert pagar.json()["status"] == "pendente"

    monkeypatch.setattr(pp.MercadoPagoProvider, "consultar_status", lambda self, ref: "approved")

    resposta = client.post("/api/webhooks/mercadopago", json={"type": "payment", "data": {"id": "PAY-WEBHOOK-FATURA-1"}})
    assert resposta.status_code == 200

    fatura_db = db.get(FaturaEmpresa, fatura_id)
    db.refresh(fatura_db)
    assert fatura_db.status == StatusFatura.PAGA


def test_webhook_ignora_notificacao_sem_id(client):
    resposta = client.post("/api/webhooks/mercadopago", json={"type": "payment", "data": {}})
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ignorado"


def test_webhook_com_payment_id_desconhecido_nao_quebra(client):
    resposta = client.post("/api/webhooks/mercadopago", json={"type": "payment", "data": {"id": "NAO-EXISTE"}})
    assert resposta.status_code == 200
    assert resposta.json()["status"] in ("sem_credencial", "nao_encontrado")
