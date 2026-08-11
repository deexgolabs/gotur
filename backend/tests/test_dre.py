from datetime import date, datetime, timedelta

from app.models.enums import StatusFatura
from app.models.fatura_empresa import FaturaEmpresa
from app.models.plano import Plano
from tests.helpers import auth_header, criar_empresa_completa, login


def _periodo_amplo():
    hoje = date.today()
    return (hoje - timedelta(days=1)).isoformat(), (hoje + timedelta(days=2)).isoformat()


def _vender_passagem(client, headers, viagem_id, **overrides):
    mapa = client.get(f"/api/viagens/{viagem_id}/poltronas", headers=headers).json()
    poltrona_id = next(p["poltrona_viagem_id"] for p in mapa if p["status"] == "livre")
    dados = {
        "poltrona_viagem_id": poltrona_id,
        "cliente_nome": "Fulano",
        "cliente_documento": "000.000.000-00",
        "forma_pagamento": "cartao",
    }
    dados.update(overrides)
    resposta = client.post(f"/api/viagens/{viagem_id}/passagens", json=dados, headers=headers)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["passagem"]


def test_dre_soma_receita_de_passagens(client, db):
    empresa = criar_empresa_completa(db, "DRE1")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    _vender_passagem(client, headers, empresa["viagem_id"])

    inicio, fim = _periodo_amplo()
    dre = client.get(f"/api/relatorios/dre?inicio={inicio}&fim={fim}", headers=headers).json()
    assert dre["receita_passagens"] == 100.0
    assert dre["receita_fretamento"] == 0.0
    assert dre["receita_frete"] == 0.0
    assert dre["receita_bruta_total"] == 100.0
    assert dre["receita_liquida"] == 100.0


def test_dre_desconta_reembolso(client, db):
    empresa = criar_empresa_completa(db, "DRE2")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    passagem = _vender_passagem(client, headers, empresa["viagem_id"])
    client.post(f"/api/viagens/{empresa['viagem_id']}/passagens/{passagem['id']}/cancelar", headers=headers)
    reembolso = client.post(
        f"/api/viagens/{empresa['viagem_id']}/passagens/{passagem['id']}/reembolsar",
        json={"motivo": "Desistência", "valor": 40.0},
        headers=headers,
    )
    assert reembolso.status_code == 200

    inicio, fim = _periodo_amplo()
    dre = client.get(f"/api/relatorios/dre?inicio={inicio}&fim={fim}", headers=headers).json()
    assert dre["receita_passagens"] == 100.0
    assert dre["reembolsos"] == 40.0
    assert dre["receita_liquida"] == 60.0


def test_dre_inclui_fretamento_e_frete(client, db):
    empresa = criar_empresa_completa(db, "DRE3")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    client.post(
        "/api/fretamentos",
        json={
            "cliente_nome": "Cliente Fretamento",
            "origem": "A",
            "destino": "B",
            "data_hora_saida": "2026-09-01T06:00:00",
            "valor_total": 500.0,
        },
        headers=headers,
    )
    client.post(
        "/api/fretes",
        json={
            "remetente_nome": "Remetente",
            "destinatario_nome": "Destinatario",
            "origem": "A",
            "destino": "B",
            "data_hora_coleta": "2026-09-01T06:00:00",
            "valor_total": 200.0,
        },
        headers=headers,
    )

    inicio, fim = _periodo_amplo()
    dre = client.get(f"/api/relatorios/dre?inicio={inicio}&fim={fim}", headers=headers).json()
    assert dre["receita_fretamento"] == 500.0
    assert dre["receita_frete"] == 200.0
    assert dre["receita_bruta_total"] == 700.0


def test_dre_desconta_assinatura_paga_no_periodo(client, db):
    empresa = criar_empresa_completa(db, "DRE4")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    plano = Plano(nome="Plano DRE", preco_mensal=99.0)
    db.add(plano)
    db.flush()
    fatura = FaturaEmpresa(
        empresa_id=empresa["empresa_id"],
        plano_id=plano.id,
        valor=99.0,
        status=StatusFatura.PAGA,
        vencimento=date.today(),
        pago_em=datetime.utcnow(),
    )
    db.add(fatura)
    db.commit()

    inicio, fim = _periodo_amplo()
    dre = client.get(f"/api/relatorios/dre?inicio={inicio}&fim={fim}", headers=headers).json()
    assert dre["despesa_assinatura_gotur"] == 99.0
    assert dre["receita_liquida"] == -99.0


def test_dre_e_isolado_por_empresa(client, db):
    empresa_a = criar_empresa_completa(db, "DRE5")
    empresa_b = criar_empresa_completa(db, "DRE6")
    headers_a = auth_header(login(client, empresa_a["admin_email"], empresa_a["senha"]))
    headers_b = auth_header(login(client, empresa_b["admin_email"], empresa_b["senha"]))

    _vender_passagem(client, headers_a, empresa_a["viagem_id"])

    inicio, fim = _periodo_amplo()
    dre_b = client.get(f"/api/relatorios/dre?inicio={inicio}&fim={fim}", headers=headers_b).json()
    assert dre_b["receita_passagens"] == 0.0
