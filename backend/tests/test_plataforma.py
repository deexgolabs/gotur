from datetime import date, datetime, timedelta

from app.database import SessionLocal
from app.models.empresa import Empresa
from app.models.enums import StatusAssinatura, StatusFatura
from app.models.fatura_empresa import FaturaEmpresa
from app.models.plano import Plano
from tests.helpers import auth_header, criar_empresa_completa, criar_super_admin, login


def _empresa_com_plano(db, sufixo: str, preco_mensal: float = 100.0):
    plano = Plano(nome=f"Plano {sufixo}", preco_mensal=preco_mensal)
    db.add(plano)
    db.flush()
    empresa = criar_empresa_completa(db, sufixo)
    db_empresa = db.get(Empresa, empresa["empresa_id"])
    db_empresa.plano_id = plano.id
    db_empresa.status_assinatura = StatusAssinatura.ATIVA
    db.commit()
    return empresa, plano


def _vender_passagem(client, headers, viagem_id, quando: datetime | None = None):
    mapa = client.get(f"/api/viagens/{viagem_id}/poltronas", headers=headers).json()
    poltrona_id = next(p["poltrona_viagem_id"] for p in mapa if p["status"] == "livre")
    resposta = client.post(
        f"/api/viagens/{viagem_id}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": "Fulano",
            "cliente_documento": "000.000.000-00",
            "forma_pagamento": "cartao",
        },
        headers=headers,
    )
    assert resposta.status_code == 201, resposta.text
    passagem_id = resposta.json()["passagem"]["id"]

    if quando is not None:
        # Ajusta criado_em direto no banco pra simular uma venda em outro
        # período — a API sempre usa "agora", não dá pra controlar por fora.
        session = SessionLocal()
        from app.models.passagem import Passagem

        p = session.get(Passagem, passagem_id)
        p.criado_em = quando
        session.commit()
        session.close()

    return passagem_id


def test_mrr_historico_inclui_fatura_paga_no_mes_atual(client, db):
    empresa, plano = _empresa_com_plano(db, "PLAT1", preco_mensal=150.0)
    super_admin = criar_super_admin(db, "PLAT1")
    headers_super = auth_header(login(client, super_admin["email"], super_admin["senha"]))

    fatura = FaturaEmpresa(
        empresa_id=empresa["empresa_id"],
        plano_id=plano.id,
        valor=150.0,
        status=StatusFatura.PAGA,
        vencimento=date.today(),
        pago_em=datetime.utcnow(),
    )
    db.add(fatura)
    db.commit()

    metricas = client.get("/api/plataforma/metricas", headers=headers_super).json()
    mes_atual = date.today().strftime("%Y-%m")
    linha_mes_atual = next(m for m in metricas["mrr_historico"] if m["mes"] == mes_atual)
    assert linha_mes_atual["mrr"] == 150.0
    assert len(metricas["mrr_historico"]) == 6


def test_inadimplencia_total_e_empresa_em_risco(client, db):
    empresa, plano = _empresa_com_plano(db, "PLAT2", preco_mensal=200.0)
    super_admin = criar_super_admin(db, "PLAT2")
    headers_super = auth_header(login(client, super_admin["email"], super_admin["senha"]))

    fatura_vencida = FaturaEmpresa(
        empresa_id=empresa["empresa_id"],
        plano_id=plano.id,
        valor=200.0,
        status=StatusFatura.PENDENTE,
        vencimento=date.today() - timedelta(days=5),
    )
    db.add(fatura_vencida)
    db.commit()

    metricas = client.get("/api/plataforma/metricas", headers=headers_super).json()
    assert metricas["inadimplencia_total"] == 200.0
    assert metricas["empresas_inadimplentes"] == 1

    risco = next(e for e in metricas["empresas_em_risco"] if e["empresa_id"] == empresa["empresa_id"])
    assert risco["valor_em_atraso"] == 200.0
    assert risco["dias_em_atraso"] >= 5
    assert risco["status_assinatura"] == "inadimplente"


def test_top_crescimento_reflete_vendas_recentes(client, db):
    empresa, _plano = _empresa_com_plano(db, "PLAT3")
    headers_empresa = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    super_admin = criar_super_admin(db, "PLAT3")
    headers_super = auth_header(login(client, super_admin["email"], super_admin["senha"]))

    _vender_passagem(client, headers_empresa, empresa["viagem_id"])

    metricas = client.get("/api/plataforma/metricas", headers=headers_super).json()
    linha = next(c for c in metricas["top_crescimento"] if c["empresa_id"] == empresa["empresa_id"])
    assert linha["passagens_mes_atual"] == 1
    assert linha["passagens_mes_anterior"] == 0
    assert linha["variacao_percentual"] is None


def test_empresas_desativadas_conta_no_resumo(client, db):
    empresa, _plano = _empresa_com_plano(db, "PLAT4")
    super_admin = criar_super_admin(db, "PLAT4")
    headers_super = auth_header(login(client, super_admin["email"], super_admin["senha"]))

    client.patch(f"/api/empresas/{empresa['empresa_id']}/desativar", headers=headers_super)

    metricas = client.get("/api/plataforma/metricas", headers=headers_super).json()
    assert metricas["empresas_desativadas"] == 1
