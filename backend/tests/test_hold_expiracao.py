from datetime import datetime, timedelta, timezone

from app.models.ocupacao_poltrona import OcupacaoPoltrona
from tests.helpers import auth_header, criar_empresa_completa, login


def _primeira_poltrona(client, viagem_id, headers):
    mapa = client.get(f"/api/viagens/{viagem_id}/poltronas", headers=headers).json()
    return mapa[0]["poltrona_viagem_id"]


def test_hold_impede_segunda_reserva_da_mesma_poltrona(client, db):
    empresa = criar_empresa_completa(db, "H1")
    token = login(client, empresa["funcionario_email"], empresa["senha"])
    headers = auth_header(token)
    poltrona_id = _primeira_poltrona(client, empresa["viagem_id"], headers)

    r1 = client.post(f"/api/viagens/{empresa['viagem_id']}/poltronas/{poltrona_id}/hold", headers=headers)
    assert r1.status_code == 200
    assert r1.json()["status"] == "hold"

    r2 = client.post(f"/api/viagens/{empresa['viagem_id']}/poltronas/{poltrona_id}/hold", headers=headers)
    assert r2.status_code == 409


def test_hold_expirado_libera_poltrona_automaticamente(client, db):
    empresa = criar_empresa_completa(db, "H2")
    token = login(client, empresa["funcionario_email"], empresa["senha"])
    headers = auth_header(token)
    poltrona_id = _primeira_poltrona(client, empresa["viagem_id"], headers)

    client.post(f"/api/viagens/{empresa['viagem_id']}/poltronas/{poltrona_id}/hold", headers=headers)

    # força o hold a já estar expirado, direto no banco
    ocupacao = db.query(OcupacaoPoltrona).filter(OcupacaoPoltrona.poltrona_viagem_id == poltrona_id).first()
    ocupacao.expira_em = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    mapa = client.get(f"/api/viagens/{empresa['viagem_id']}/poltronas", headers=headers).json()
    poltrona = next(p for p in mapa if p["poltrona_viagem_id"] == poltrona_id)
    assert poltrona["status"] == "livre"

    r2 = client.post(f"/api/viagens/{empresa['viagem_id']}/poltronas/{poltrona_id}/hold", headers=headers)
    assert r2.status_code == 200
