from datetime import date, datetime, timedelta

from app.models.academia import FaturaMatricula
from app.models.enums import StatusFatura
from app.models.evento import AssentoSessao
from app.models.fatura_empresa import FaturaEmpresa
from app.models.plano import Plano
from app.models.usuario import Usuario
from tests.helpers import auth_header, criar_cliente, criar_empresa_completa, login


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


def test_dre_inclui_eventos_e_academia(client, db):
    """Regressão: DRE só somava passagens/fretamento/frete — receita de
    ingresso (eventos) e mensalidade (academia) nunca entravam na conta,
    mesmo pra empresa com esses módulos ativos."""
    empresa = criar_empresa_completa(db, "DRE7")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    local = client.post(
        "/api/locais",
        json={"nome": "Teatro DRE7", "total_assentos": 4},
        headers=headers,
    )
    assert local.status_code == 201, local.text
    sessao = client.post(
        "/api/sessoes",
        json={
            "local_id": local.json()["id"],
            "nome_evento": "Show DRE7",
            "data_hora": (datetime.now() + timedelta(days=5)).isoformat(),
            "preco": 80.0,
        },
        headers=headers,
    )
    assert sessao.status_code == 201, sessao.text
    sessao_id = sessao.json()["id"]
    assento_id = db.query(AssentoSessao).filter(AssentoSessao.sessao_id == sessao_id).first().id
    hold = client.post(f"/api/sessoes/{sessao_id}/assentos/{assento_id}/hold", headers=headers)
    assert hold.status_code == 200, hold.text
    ingresso = client.post(
        f"/api/sessoes/{sessao_id}/ingressos",
        json={
            "assento_sessao_id": assento_id,
            "cliente_nome": "Comprador Evento",
            "cliente_documento": "111.111.111-11",
            "forma_pagamento": "dinheiro",
        },
        headers=headers,
    )
    assert ingresso.status_code == 201, ingresso.text

    turma = client.post(
        "/api/turmas",
        json={
            "nome": "Turma DRE7",
            "dia_semana": 1,
            "hora_inicio": "10:00:00",
            "duracao_minutos": 45,
            "capacidade_vagas": 10,
        },
        headers=headers,
    )
    assert turma.status_code == 201, turma.text
    cliente = criar_cliente(db, "DRE7")
    cliente_usuario_id = db.query(Usuario).filter_by(email=cliente["email"]).first().id
    matricula = client.post(
        "/api/matriculas",
        json={"cliente_usuario_id": cliente_usuario_id, "tipo": "mensal_ilimitado", "valor_mensalidade": 150.0},
        headers=headers,
    )
    assert matricula.status_code == 201, matricula.text
    fatura = db.query(FaturaMatricula).filter(FaturaMatricula.matricula_id == matricula.json()["id"]).first()
    fatura.status = StatusFatura.PAGA
    fatura.pago_em = datetime.utcnow()
    db.commit()

    inicio, fim = _periodo_amplo()
    dre = client.get(f"/api/relatorios/dre?inicio={inicio}&fim={fim}", headers=headers).json()
    assert dre["receita_eventos"] == 80.0
    assert dre["receita_academia"] == 150.0
    assert dre["receita_bruta_total"] == 230.0
    assert dre["receita_liquida"] == 230.0


def test_dre_e_isolado_por_empresa(client, db):
    empresa_a = criar_empresa_completa(db, "DRE5")
    empresa_b = criar_empresa_completa(db, "DRE6")
    headers_a = auth_header(login(client, empresa_a["admin_email"], empresa_a["senha"]))
    headers_b = auth_header(login(client, empresa_b["admin_email"], empresa_b["senha"]))

    _vender_passagem(client, headers_a, empresa_a["viagem_id"])

    inicio, fim = _periodo_amplo()
    dre_b = client.get(f"/api/relatorios/dre?inicio={inicio}&fim={fim}", headers=headers_b).json()
    assert dre_b["receita_passagens"] == 0.0
