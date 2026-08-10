from datetime import datetime, timedelta

from app.models.onibus import Onibus, PoltronaOnibus
from app.models.poltrona_viagem import PoltronaViagem
from app.models.viagem import Viagem
from tests.helpers import auth_header, criar_empresa_completa, criar_rota_com_paradas, login


def _criar_viagem_com_paradas(db, empresa):
    rota = criar_rota_com_paradas(
        db,
        empresa["empresa_id"],
        [("A", 2), ("B", 1), ("C", None)],
    )
    onibus = db.query(Onibus).filter(Onibus.id == empresa["onibus_id"]).first()
    viagem = Viagem(
        tenant_id=empresa["empresa_id"],
        rota_id=rota.id,
        onibus_id=onibus.id,
        data_hora_partida=datetime.now() + timedelta(days=2),
        preco=90.0,
    )
    db.add(viagem)
    db.flush()
    for p in db.query(PoltronaOnibus).filter(PoltronaOnibus.onibus_id == onibus.id).all():
        db.add(PoltronaViagem(viagem_id=viagem.id, poltrona_onibus_id=p.id))
    db.commit()
    db.refresh(viagem)

    paradas = {p.nome: p.id for p in rota.paradas}
    return viagem.id, paradas


def _vender(client, headers, viagem_id, poltrona_id, origem_id, destino_id, nome="Fulano"):
    return client.post(
        f"/api/viagens/{viagem_id}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": nome,
            "cliente_documento": "000.000.000-00",
            "forma_pagamento": "cartao",
            "parada_origem_id": origem_id,
            "parada_destino_id": destino_id,
        },
        headers=headers,
    )


def test_mesma_poltrona_vendida_em_dois_trechos_diferentes(client, db):
    empresa = criar_empresa_completa(db, "T1")
    viagem_id, paradas = _criar_viagem_com_paradas(db, empresa)
    token = login(client, empresa["funcionario_email"], empresa["senha"])
    headers = auth_header(token)

    mapa = client.get(f"/api/viagens/{viagem_id}/poltronas", headers=headers).json()
    poltrona_id = mapa[0]["poltrona_viagem_id"]

    # peso total = 2 + 1 = 3; preco viagem = 90
    r_ab = _vender(client, headers, viagem_id, poltrona_id, paradas["A"], paradas["B"], "Passageiro AB")
    assert r_ab.status_code == 201, r_ab.text
    assert r_ab.json()["passagem"]["preco"] == 60.0  # (2/3) * 90

    r_bc = _vender(client, headers, viagem_id, poltrona_id, paradas["B"], paradas["C"], "Passageiro BC")
    assert r_bc.status_code == 201, r_bc.text
    assert r_bc.json()["passagem"]["preco"] == 30.0  # (1/3) * 90


def test_overselling_do_mesmo_trecho_e_bloqueado(client, db):
    empresa = criar_empresa_completa(db, "T2")
    viagem_id, paradas = _criar_viagem_com_paradas(db, empresa)
    token = login(client, empresa["funcionario_email"], empresa["senha"])
    headers = auth_header(token)

    mapa = client.get(f"/api/viagens/{viagem_id}/poltronas", headers=headers).json()
    poltrona_id = mapa[0]["poltrona_viagem_id"]

    r1 = _vender(client, headers, viagem_id, poltrona_id, paradas["A"], paradas["C"])
    assert r1.status_code == 201

    # tenta vender um sub-trecho que já está coberto pela venda anterior
    r2 = _vender(client, headers, viagem_id, poltrona_id, paradas["A"], paradas["B"])
    assert r2.status_code == 409


def test_cancelamento_libera_so_o_trecho_cancelado(client, db):
    empresa = criar_empresa_completa(db, "T3")
    viagem_id, paradas = _criar_viagem_com_paradas(db, empresa)
    token = login(client, empresa["funcionario_email"], empresa["senha"])
    headers = auth_header(token)

    mapa = client.get(f"/api/viagens/{viagem_id}/poltronas", headers=headers).json()
    poltrona_id = mapa[0]["poltrona_viagem_id"]

    passagem_ab = _vender(client, headers, viagem_id, poltrona_id, paradas["A"], paradas["B"]).json()["passagem"]
    _vender(client, headers, viagem_id, poltrona_id, paradas["B"], paradas["C"])

    cancelar = client.post(
        f"/api/viagens/{viagem_id}/passagens/{passagem_ab['id']}/cancelar", headers=headers
    )
    assert cancelar.status_code == 200

    mapa_ab = client.get(
        f"/api/viagens/{viagem_id}/poltronas?origem_parada_id={paradas['A']}&destino_parada_id={paradas['B']}",
        headers=headers,
    ).json()
    assert next(p for p in mapa_ab if p["poltrona_viagem_id"] == poltrona_id)["status"] == "livre"

    mapa_bc = client.get(
        f"/api/viagens/{viagem_id}/poltronas?origem_parada_id={paradas['B']}&destino_parada_id={paradas['C']}",
        headers=headers,
    ).json()
    assert next(p for p in mapa_bc if p["poltrona_viagem_id"] == poltrona_id)["status"] == "vendida"
