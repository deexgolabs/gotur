from datetime import datetime, timedelta

from app.models.empresa import Empresa
from app.models.enums import StatusRepasse
from app.models.interline import AcertoInterline, ConexaoInterline
from app.models.onibus import PoltronaOnibus
from app.models.poltrona_viagem import PoltronaViagem
from app.models.viagem import Viagem
from tests.helpers import auth_header, criar_cliente, criar_empresa_completa, criar_rota_com_paradas, criar_super_admin, login


def _duas_empresas_conectadas(db):
    """Empresa SP1 cobre São Paulo -> Ribeirão Preto; Empresa SP2 cobre
    Ribeirão Preto -> Uberlândia. Cria uma Viagem em cada, no mesmo dia,
    com a perna B partindo depois da perna A."""
    empresa_a = criar_empresa_completa(db, "IL1")
    empresa_b = criar_empresa_completa(db, "IL2")

    rota_a = criar_rota_com_paradas(db, empresa_a["empresa_id"], [("São Paulo", 1.0), ("Ribeirão Preto", None)])
    rota_b = criar_rota_com_paradas(db, empresa_b["empresa_id"], [("Ribeirão Preto", 1.0), ("Uberlândia", None)])

    partida_a = datetime.now() + timedelta(days=1, hours=8)
    partida_b = partida_a + timedelta(hours=4)

    viagem_a = Viagem(tenant_id=empresa_a["empresa_id"], rota_id=rota_a.id, onibus_id=empresa_a["onibus_id"], data_hora_partida=partida_a, preco=100.0)
    db.add(viagem_a)
    db.flush()
    for p in db.query(PoltronaOnibus).filter(PoltronaOnibus.onibus_id == empresa_a["onibus_id"]).all():
        db.add(PoltronaViagem(viagem_id=viagem_a.id, poltrona_onibus_id=p.id))

    viagem_b = Viagem(tenant_id=empresa_b["empresa_id"], rota_id=rota_b.id, onibus_id=empresa_b["onibus_id"], data_hora_partida=partida_b, preco=80.0)
    db.add(viagem_b)
    db.flush()
    for p in db.query(PoltronaOnibus).filter(PoltronaOnibus.onibus_id == empresa_b["onibus_id"]).all():
        db.add(PoltronaViagem(viagem_id=viagem_b.id, poltrona_onibus_id=p.id))

    db.commit()

    return {
        "empresa_a": empresa_a,
        "empresa_b": empresa_b,
        "rota_a_id": rota_a.id,
        "rota_b_id": rota_b.id,
        "viagem_a_id": viagem_a.id,
        "viagem_b_id": viagem_b.id,
        "data": partida_a.date(),
    }


def _criar_conexao(client, headers_super, cenario, minutos_conexao_minima=30):
    resposta = client.post(
        "/api/interline/conexoes",
        json={
            "rota_perna_a_id": cenario["rota_a_id"],
            "rota_perna_b_id": cenario["rota_b_id"],
            "parada_conexao_nome": "Ribeirão Preto",
            "minutos_conexao_minima": minutos_conexao_minima,
        },
        headers=headers_super,
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _poltrona_livre(db, viagem_id):
    return db.query(PoltronaViagem).filter(PoltronaViagem.viagem_id == viagem_id).first().id


def test_criar_conexao_exige_super_admin(client, db):
    cenario = _duas_empresas_conectadas(db)
    headers_empresa = auth_header(login(client, cenario["empresa_a"]["admin_email"], cenario["empresa_a"]["senha"]))

    resposta = client.post(
        "/api/interline/conexoes",
        json={"rota_perna_a_id": cenario["rota_a_id"], "rota_perna_b_id": cenario["rota_b_id"], "parada_conexao_nome": "X"},
        headers=headers_empresa,
    )
    assert resposta.status_code == 403


def test_criar_conexao_recusa_mesma_empresa_nas_duas_pernas(client, db):
    empresa = criar_empresa_completa(db, "IL3")
    rota_a = criar_rota_com_paradas(db, empresa["empresa_id"], [("X", 1.0), ("Y", None)])
    rota_b = criar_rota_com_paradas(db, empresa["empresa_id"], [("Y", 1.0), ("Z", None)])
    super_admin = criar_super_admin(db, "IL3")
    headers_super = auth_header(login(client, super_admin["email"], super_admin["senha"]))

    resposta = client.post(
        "/api/interline/conexoes",
        json={"rota_perna_a_id": rota_a.id, "rota_perna_b_id": rota_b.id, "parada_conexao_nome": "Y"},
        headers=headers_super,
    )
    assert resposta.status_code == 400


def test_buscar_encontra_itinerario_compativel(client, db):
    cenario = _duas_empresas_conectadas(db)
    super_admin = criar_super_admin(db, "IL4")
    headers_super = auth_header(login(client, super_admin["email"], super_admin["senha"]))
    _criar_conexao(client, headers_super, cenario)

    resposta = client.get(
        "/api/interline/buscar", params={"origem": "São Paulo", "destino": "Uberlândia", "data": cenario["data"].isoformat()}
    )
    assert resposta.status_code == 200, resposta.text
    opcoes = resposta.json()
    assert len(opcoes) == 1
    opcao = opcoes[0]
    assert opcao["viagem_perna_a_id"] == cenario["viagem_a_id"]
    assert opcao["viagem_perna_b_id"] == cenario["viagem_b_id"]
    assert opcao["valor_perna_a"] == 100.0
    assert opcao["valor_perna_b"] == 80.0
    assert opcao["valor_total"] == 180.0


def test_buscar_nao_encontra_fora_da_janela_de_conexao(client, db):
    cenario = _duas_empresas_conectadas(db)
    super_admin = criar_super_admin(db, "IL5")
    headers_super = auth_header(login(client, super_admin["email"], super_admin["senha"]))
    # Exige 6h de conexão mínima, mas a perna B só parte 4h depois da A.
    _criar_conexao(client, headers_super, cenario, minutos_conexao_minima=6 * 60)

    resposta = client.get(
        "/api/interline/buscar", params={"origem": "São Paulo", "destino": "Uberlândia", "data": cenario["data"].isoformat()}
    )
    assert resposta.status_code == 200
    assert resposta.json() == []


def test_comprar_interline_com_cartao_cria_duas_passagens_e_acerto(client, db):
    cenario = _duas_empresas_conectadas(db)
    super_admin = criar_super_admin(db, "IL6")
    headers_super = auth_header(login(client, super_admin["email"], super_admin["senha"]))
    conexao = _criar_conexao(client, headers_super, cenario)

    cliente = criar_cliente(db, "IL6")
    headers_cliente = auth_header(login(client, cliente["email"], cliente["senha"]))

    resposta = client.post(
        "/api/interline/pedidos",
        json={
            "conexao_id": conexao["id"],
            "viagem_perna_a_id": cenario["viagem_a_id"],
            "poltrona_perna_a_id": _poltrona_livre(db, cenario["viagem_a_id"]),
            "viagem_perna_b_id": cenario["viagem_b_id"],
            "poltrona_perna_b_id": _poltrona_livre(db, cenario["viagem_b_id"]),
            "cliente_nome": "Fulano Interline",
            "cliente_documento": "000.000.000-00",
            "forma_pagamento": "cartao",
            "mp_token": "TOK",
            "mp_payment_method_id": "visa",
        },
        headers=headers_cliente,
    )
    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["localizador_perna_a"]
    assert corpo["localizador_perna_b"]
    assert corpo["localizador_perna_a"] != corpo["localizador_perna_b"]

    # Cada passagem foi criada no tenant certo.
    passagens_a = client.get(f"/api/viagens/{cenario['viagem_a_id']}/passagens", headers=headers_super).json()
    passagens_b = client.get(f"/api/viagens/{cenario['viagem_b_id']}/passagens", headers=headers_super).json()
    assert len(passagens_a) == 1 and passagens_a[0]["preco"] == 100.0
    assert len(passagens_b) == 1 and passagens_b[0]["preco"] == 80.0

    acerto = db.query(AcertoInterline).filter(AcertoInterline.empresa_devedora_id == cenario["empresa_a"]["empresa_id"]).first()
    assert acerto is not None
    assert float(acerto.valor_devido) == 80.0
    assert acerto.empresa_credora_id == cenario["empresa_b"]["empresa_id"]
    assert acerto.status == StatusRepasse.PENDENTE


def test_comprar_interline_com_pix_fica_pendente_e_confirmar_simulado_libera(client, db):
    cenario = _duas_empresas_conectadas(db)
    super_admin = criar_super_admin(db, "IL7")
    headers_super = auth_header(login(client, super_admin["email"], super_admin["senha"]))
    conexao = _criar_conexao(client, headers_super, cenario)

    cliente = criar_cliente(db, "IL7")
    headers_cliente = auth_header(login(client, cliente["email"], cliente["senha"]))

    resposta = client.post(
        "/api/interline/pedidos",
        json={
            "conexao_id": conexao["id"],
            "viagem_perna_a_id": cenario["viagem_a_id"],
            "poltrona_perna_a_id": _poltrona_livre(db, cenario["viagem_a_id"]),
            "viagem_perna_b_id": cenario["viagem_b_id"],
            "poltrona_perna_b_id": _poltrona_livre(db, cenario["viagem_b_id"]),
            "cliente_nome": "Ciclana Interline",
            "cliente_documento": "111.111.111-11",
            "forma_pagamento": "pix",
        },
        headers=headers_cliente,
    )
    assert resposta.status_code == 201, resposta.text
    pedido = resposta.json()["pedido_interline"]
    assert pedido["status"] == "pendente_pagamento"
    assert pedido["pix_copia_cola"]
    assert pedido["passagem_perna_a_id"] is None

    # As duas poltronas ficam em hold — outro CLIENTE (não staff) não pode
    # comprar a mesma poltrona por cima (staff pode, por design — mesmo
    # comportamento de vender_passagem em app/routers/passagens.py).
    headers_outro_cliente = auth_header(login(client, criar_cliente(db, "IL7B")["email"], "senha123"))
    conflito = client.post(
        "/api/interline/pedidos",
        json={
            "conexao_id": conexao["id"],
            "viagem_perna_a_id": cenario["viagem_a_id"],
            "poltrona_perna_a_id": _poltrona_livre(db, cenario["viagem_a_id"]),
            "viagem_perna_b_id": cenario["viagem_b_id"],
            "poltrona_perna_b_id": _poltrona_livre(db, cenario["viagem_b_id"]),
            "cliente_nome": "Outro",
            "cliente_documento": "222.222.222-22",
            "forma_pagamento": "pix",
        },
        headers=headers_outro_cliente,
    )
    assert conflito.status_code == 409

    confirmar = client.post(f"/api/interline/pedidos/{pedido['id']}/confirmar-simulado", headers=headers_cliente)
    assert confirmar.status_code == 200, confirmar.text
    corpo = confirmar.json()
    assert corpo["localizador_perna_a"]
    assert corpo["localizador_perna_b"]

    de_novo = client.post(f"/api/interline/pedidos/{pedido['id']}/confirmar-simulado", headers=headers_cliente)
    assert de_novo.status_code == 409


def test_marcar_acerto_pago_so_empresa_credora(client, db):
    cenario = _duas_empresas_conectadas(db)
    super_admin = criar_super_admin(db, "IL8")
    headers_super = auth_header(login(client, super_admin["email"], super_admin["senha"]))
    conexao = _criar_conexao(client, headers_super, cenario)

    headers_cliente = auth_header(login(client, criar_cliente(db, "IL8")["email"], "senha123"))
    client.post(
        "/api/interline/pedidos",
        json={
            "conexao_id": conexao["id"],
            "viagem_perna_a_id": cenario["viagem_a_id"],
            "poltrona_perna_a_id": _poltrona_livre(db, cenario["viagem_a_id"]),
            "viagem_perna_b_id": cenario["viagem_b_id"],
            "poltrona_perna_b_id": _poltrona_livre(db, cenario["viagem_b_id"]),
            "cliente_nome": "Beltrano",
            "cliente_documento": "333.333.333-33",
            "forma_pagamento": "cartao",
            "mp_token": "TOK",
            "mp_payment_method_id": "visa",
        },
        headers=headers_cliente,
    )
    acerto = db.query(AcertoInterline).first()

    headers_empresa_a = auth_header(login(client, cenario["empresa_a"]["admin_email"], cenario["empresa_a"]["senha"]))
    negado = client.patch(f"/api/interline/acertos/{acerto.id}/marcar-pago", headers=headers_empresa_a)
    assert negado.status_code == 403

    headers_empresa_b = auth_header(login(client, cenario["empresa_b"]["admin_email"], cenario["empresa_b"]["senha"]))
    aceito = client.patch(f"/api/interline/acertos/{acerto.id}/marcar-pago", headers=headers_empresa_b)
    assert aceito.status_code == 200
    assert aceito.json()["status"] == "pago"


def test_acertos_isolados_entre_empresas_de_fora(client, db):
    cenario = _duas_empresas_conectadas(db)
    super_admin = criar_super_admin(db, "IL9")
    headers_super = auth_header(login(client, super_admin["email"], super_admin["senha"]))
    conexao = _criar_conexao(client, headers_super, cenario)

    headers_cliente = auth_header(login(client, criar_cliente(db, "IL9")["email"], "senha123"))
    client.post(
        "/api/interline/pedidos",
        json={
            "conexao_id": conexao["id"],
            "viagem_perna_a_id": cenario["viagem_a_id"],
            "poltrona_perna_a_id": _poltrona_livre(db, cenario["viagem_a_id"]),
            "viagem_perna_b_id": cenario["viagem_b_id"],
            "poltrona_perna_b_id": _poltrona_livre(db, cenario["viagem_b_id"]),
            "cliente_nome": "Sicrano",
            "cliente_documento": "444.444.444-44",
            "forma_pagamento": "cartao",
            "mp_token": "TOK",
            "mp_payment_method_id": "visa",
        },
        headers=headers_cliente,
    )

    empresa_c = criar_empresa_completa(db, "ILC")
    headers_empresa_c = auth_header(login(client, empresa_c["admin_email"], empresa_c["senha"]))
    resposta = client.get("/api/interline/acertos", headers=headers_empresa_c)
    assert resposta.status_code == 200
    assert resposta.json() == []
