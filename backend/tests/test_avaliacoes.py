from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models.enums import StatusFretamento
from app.models.fretamento import Fretamento
from app.models.viagem import Viagem
from tests.helpers import auth_header, criar_empresa_completa, login


def _comprar_e_confirmar(client, headers_staff, viagem_id):
    mapa = client.get(f"/api/viagens/{viagem_id}/poltronas", headers=headers_staff).json()
    poltrona_id = next(p for p in mapa if p["status"] == "livre")["poltrona_viagem_id"]
    resposta = client.post(
        f"/api/viagens/{viagem_id}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": "Fulano",
            "cliente_documento": "000.000.000-00",
            "forma_pagamento": "cartao",
        },
        headers=headers_staff,
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["passagem"]


def test_nao_pode_avaliar_viagem_que_ainda_nao_aconteceu(client, db):
    empresa = criar_empresa_completa(db, "AV1")
    cadastro = client.post(
        "/api/auth/registrar-cliente",
        json={
            "nome": "Cliente Teste",
            "email": "clienteav1@teste.com",
            "senha": "senha123456",
            "documento": "333.333.333-33",
        },
    )
    assert cadastro.status_code == 201, cadastro.text
    headers = auth_header(cadastro.json()["access_token"])
    passagem = _comprar_e_confirmar(client, headers, empresa["viagem_id"])

    resposta = client.post(f"/api/passagens/{passagem['id']}/avaliar", json={"nota": 5}, headers=headers)
    assert resposta.status_code == 409


def test_cliente_avalia_viagem_ja_realizada(client, db):
    empresa = criar_empresa_completa(db, "AV2")

    # Cliente compra a própria passagem (precisa estar logado como cliente).
    cadastro = client.post(
        "/api/auth/registrar-cliente",
        json={
            "nome": "Cliente Teste",
            "email": "clienteav2@teste.com",
            "senha": "senha123456",
            "documento": "222.222.222-22",
        },
    )
    assert cadastro.status_code == 201, cadastro.text
    token_cliente = cadastro.json()["access_token"]
    headers_cliente = auth_header(token_cliente)

    mapa = client.get(f"/api/viagens/{empresa['viagem_id']}/poltronas", headers=headers_cliente).json()
    poltrona_id = next(p for p in mapa if p["status"] == "livre")["poltrona_viagem_id"]
    compra = client.post(
        f"/api/viagens/{empresa['viagem_id']}/passagens",
        json={
            "poltrona_viagem_id": poltrona_id,
            "cliente_nome": "Cliente Teste",
            "cliente_documento": "111.111.111-11",
            "forma_pagamento": "cartao",
        },
        headers=headers_cliente,
    )
    assert compra.status_code == 201, compra.text
    passagem_id = compra.json()["passagem"]["id"]

    # Empurra a data de partida da viagem para o passado, simulando que a
    # viagem já aconteceu.
    sessao = SessionLocal()
    sessao.query(Viagem).filter(Viagem.id == empresa["viagem_id"]).update(
        {"data_hora_partida": datetime.now() - timedelta(hours=2)}
    )
    sessao.commit()
    sessao.close()

    minhas = client.get("/api/passagens/minhas", headers=headers_cliente).json()
    detalhe = next(p for p in minhas if p["id"] == passagem_id)
    assert detalhe["pode_avaliar"] is True

    avaliar = client.post(
        f"/api/passagens/{passagem_id}/avaliar", json={"nota": 4, "comentario": "Boa viagem"}, headers=headers_cliente
    )
    assert avaliar.status_code == 201, avaliar.text
    assert avaliar.json()["nota"] == 4

    de_novo = client.post(f"/api/passagens/{passagem_id}/avaliar", json={"nota": 5}, headers=headers_cliente)
    assert de_novo.status_code == 409

    minhas_depois = client.get("/api/passagens/minhas", headers=headers_cliente).json()
    detalhe_depois = next(p for p in minhas_depois if p["id"] == passagem_id)
    assert detalhe_depois["pode_avaliar"] is False
    assert detalhe_depois["nota_avaliacao"] == 4

    # A equipe da empresa vê a avaliação e a média.
    token_staff = login(client, empresa["admin_email"], empresa["senha"])
    listagem = client.get("/api/avaliacoes", headers=auth_header(token_staff))
    assert listagem.status_code == 200
    corpo = listagem.json()
    assert corpo["total"] == 1
    assert corpo["media"] == 4.0


def test_avaliacao_publica_de_fretamento_concluido(client, db):
    empresa = criar_empresa_completa(db, "AV3")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    fretamento = client.post(
        "/api/fretamentos",
        json={
            "cliente_nome": "Excursao Teste",
            "origem": "A",
            "destino": "B",
            "data_hora_saida": "2026-09-01T06:00:00",
        },
        headers=headers,
    ).json()
    codigo = fretamento["codigo_rastreio"]

    ainda_nao = client.post(f"/api/fretamentos/rastrear/{codigo}/avaliar", json={"nota": 5})
    assert ainda_nao.status_code == 409

    sessao = SessionLocal()
    sessao.query(Fretamento).filter(Fretamento.id == fretamento["id"]).update({"status": StatusFretamento.CONCLUIDO})
    sessao.commit()
    sessao.close()

    rastreio = client.get(f"/api/fretamentos/rastrear/{codigo}").json()
    assert rastreio["ja_avaliado"] is False

    avaliar = client.post(f"/api/fretamentos/rastrear/{codigo}/avaliar", json={"nota": 5, "comentario": "Ótimo"})
    assert avaliar.status_code == 201, avaliar.text

    rastreio_depois = client.get(f"/api/fretamentos/rastrear/{codigo}").json()
    assert rastreio_depois["ja_avaliado"] is True

    de_novo = client.post(f"/api/fretamentos/rastrear/{codigo}/avaliar", json={"nota": 3})
    assert de_novo.status_code == 409
