from datetime import datetime, time, timedelta

from app.core.security import hash_senha
from app.models.academia import FaturaMatricula, Matricula, OcorrenciaTurma, Turma
from app.models.empresa import Empresa
from app.models.enums import UserRole
from app.models.usuario import Usuario
from app.services.ocorrencias_turma import SEMANAS_JANELA, estender_janela_todas_turmas, gerar_ocorrencias
from tests.helpers import auth_header, criar_cliente, criar_empresa_completa, login


def _empresa_com_turma(client, db, sufixo: str, capacidade_vagas: int = 20, preco_avulso: float | None = 50.0):
    empresa = criar_empresa_completa(db, sufixo)
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    # dia_semana E hora_inicio vêm do MESMO instante de referência (agora +
    # 2h) em vez de "hoje" + hora fixa "07:00:00" — testado depois das 7h
    # UTC, a hora fixa geraria a ocorrência de hoje já no passado (409
    # "Esta aula já aconteceu" em qualquer reserva). Somar 2h ao instante
    # de referência garante ocorrência futura mesmo perto da virada do dia.
    referencia = datetime.utcnow() + timedelta(hours=2)

    resposta = client.post(
        "/api/turmas",
        json={
            "nome": f"Spinning {sufixo}",
            "dia_semana": referencia.weekday(),
            "hora_inicio": referencia.strftime("%H:%M:%S"),
            "duracao_minutos": 45,
            "capacidade_vagas": capacidade_vagas,
            "instrutor": "Professor Teste",
            "preco_avulso": preco_avulso,
        },
        headers=headers_admin,
    )
    assert resposta.status_code == 201, resposta.text
    turma = resposta.json()

    return {"empresa": empresa, "headers_admin": headers_admin, "turma": turma, "dia_semana": referencia.weekday()}


def _primeira_ocorrencia_id(db, turma_id: int) -> int:
    return (
        db.query(OcorrenciaTurma)
        .filter(OcorrenciaTurma.turma_id == turma_id)
        .order_by(OcorrenciaTurma.data_hora_inicio)
        .first()
        .id
    )


def _matricula_ativa(client, db, cenario, sufixo_cliente: str, tipo: str = "mensal_ilimitado", aulas_por_ciclo: int | None = None):
    """Cria um cliente com matrícula já paga (ATIVA) — pra testes que
    precisam reservar vaga, não do fluxo de assinatura em si. Usa a rota
    de staff (não a de loja) porque as empresas de teste não têm slug."""
    cliente = criar_cliente(db, sufixo_cliente)
    headers_cliente = auth_header(login(client, cliente["email"], cliente["senha"]))

    payload = {"cliente_usuario_id": _usuario_id_por_email(db, cliente["email"]), "tipo": tipo, "valor_mensalidade": 150.0}
    if aulas_por_ciclo is not None:
        payload["aulas_por_ciclo"] = aulas_por_ciclo

    resposta = client.post("/api/matriculas", json=payload, headers=cenario["headers_admin"])
    assert resposta.status_code == 201, resposta.text
    matricula = resposta.json()

    fatura = db.query(FaturaMatricula).filter(FaturaMatricula.matricula_id == matricula["id"]).first()
    pagar = client.post(
        f"/api/faturas-matricula/{fatura.id}/pagar",
        json={"forma_pagamento": "cartao", "mp_token": "TOK", "mp_payment_method_id": "visa"},
        headers=headers_cliente,
    )
    assert pagar.status_code == 200, pagar.text

    return {"cliente": cliente, "headers_cliente": headers_cliente, "matricula_id": matricula["id"]}


def _usuario_id_por_email(db, email: str) -> int:
    from app.models.usuario import Usuario

    return db.query(Usuario).filter(Usuario.email == email).first().id


def test_criar_turma_gera_ocorrencias_da_janela(client, db):
    cenario = _empresa_com_turma(client, db, "AC1")
    ocorrencias = db.query(OcorrenciaTurma).filter(OcorrenciaTurma.turma_id == cenario["turma"]["id"]).all()
    # dia_semana = o de referência (ver _empresa_com_turma), então a
    # primeira ocorrência cai nele e depois semana a semana até a janela
    # de SEMANAS_JANELA semanas à frente.
    assert len(ocorrencias) == SEMANAS_JANELA + 1
    for o in ocorrencias:
        assert o.data_hora_inicio.weekday() == cenario["dia_semana"]
        assert o.capacidade_vagas == 20


def test_gerar_ocorrencias_e_idempotente(client, db):
    cenario = _empresa_com_turma(client, db, "AC2")
    turma = db.get(Turma, cenario["turma"]["id"])

    antes = db.query(OcorrenciaTurma).filter(OcorrenciaTurma.turma_id == turma.id).count()
    novas = gerar_ocorrencias(db, turma)
    depois = db.query(OcorrenciaTurma).filter(OcorrenciaTurma.turma_id == turma.id).count()

    assert novas == []
    assert antes == depois

    total = estender_janela_todas_turmas(db)
    assert total == 0


def test_matricula_cria_primeira_fatura_pendente(client, db):
    cenario = _empresa_com_turma(client, db, "AC3")
    cliente = criar_cliente(db, "AC3")
    usuario_id = _usuario_id_por_email(db, cliente["email"])

    resposta = client.post(
        "/api/matriculas",
        json={"cliente_usuario_id": usuario_id, "tipo": "mensal_ilimitado", "valor_mensalidade": 150.0},
        headers=cenario["headers_admin"],
    )
    assert resposta.status_code == 201, resposta.text
    matricula = resposta.json()
    assert matricula["status"] == "pendente"

    fatura = db.query(FaturaMatricula).filter(FaturaMatricula.matricula_id == matricula["id"]).first()
    assert fatura is not None
    assert fatura.status.value == "pendente"
    assert float(fatura.valor) == 150.0


def test_pagar_fatura_matricula_com_cartao_ativa_matricula(client, db):
    cenario = _empresa_com_turma(client, db, "AC4")
    cliente = criar_cliente(db, "AC4")
    headers_cliente = auth_header(login(client, cliente["email"], cliente["senha"]))
    usuario_id = _usuario_id_por_email(db, cliente["email"])

    matricula = client.post(
        "/api/matriculas",
        json={"cliente_usuario_id": usuario_id, "tipo": "mensal_ilimitado", "valor_mensalidade": 150.0},
        headers=cenario["headers_admin"],
    ).json()
    fatura = db.query(FaturaMatricula).filter(FaturaMatricula.matricula_id == matricula["id"]).first()

    pagar = client.post(
        f"/api/faturas-matricula/{fatura.id}/pagar",
        json={"forma_pagamento": "cartao", "mp_token": "TOK", "mp_payment_method_id": "visa"},
        headers=headers_cliente,
    )
    assert pagar.status_code == 200, pagar.text
    assert pagar.json()["status"] == "paga"

    db.expire_all()
    matricula_db = db.get(Matricula, matricula["id"])
    assert matricula_db.status.value == "ativa"


def test_relatorio_vendas_academia_soma_faturas_pagas(client, db):
    cenario = _empresa_com_turma(client, db, "AC17")
    aluno = _matricula_ativa(client, db, cenario, "AC17")

    hoje = datetime.utcnow().date()
    inicio = (hoje - timedelta(days=1)).isoformat()
    fim = (hoje + timedelta(days=1)).isoformat()
    relatorio = client.get(f"/api/relatorios/vendas-academia?inicio={inicio}&fim={fim}", headers=cenario["headers_admin"])
    assert relatorio.status_code == 200, relatorio.text
    corpo = relatorio.json()
    assert corpo["total_itens"] == 1
    assert corpo["total_arrecadado"] == 150.0
    assert corpo["por_forma_pagamento"]["cartao"] == 150.0


def test_pagar_fatura_matricula_com_pix_fica_pendente_e_confirmar_simulado_ativa(client, db):
    cenario = _empresa_com_turma(client, db, "AC5")
    cliente = criar_cliente(db, "AC5")
    headers_cliente = auth_header(login(client, cliente["email"], cliente["senha"]))
    usuario_id = _usuario_id_por_email(db, cliente["email"])

    matricula = client.post(
        "/api/matriculas",
        json={"cliente_usuario_id": usuario_id, "tipo": "mensal_ilimitado", "valor_mensalidade": 150.0},
        headers=cenario["headers_admin"],
    ).json()
    fatura = db.query(FaturaMatricula).filter(FaturaMatricula.matricula_id == matricula["id"]).first()

    pagar = client.post(f"/api/faturas-matricula/{fatura.id}/pagar", json={"forma_pagamento": "pix"}, headers=headers_cliente)
    assert pagar.status_code == 200, pagar.text
    corpo = pagar.json()
    assert corpo["status"] == "pendente"
    assert corpo["pix_copia_cola"]

    confirmar = client.post(f"/api/faturas-matricula/{fatura.id}/confirmar-simulado", headers=headers_cliente)
    assert confirmar.status_code == 200, confirmar.text
    assert confirmar.json()["status"] == "paga"

    de_novo = client.post(f"/api/faturas-matricula/{fatura.id}/confirmar-simulado", headers=headers_cliente)
    assert de_novo.status_code == 409

    db.expire_all()
    matricula_db = db.get(Matricula, matricula["id"])
    assert matricula_db.status.value == "ativa"


def test_reservar_vaga_respeita_capacidade_da_ocorrencia(client, db):
    cenario = _empresa_com_turma(client, db, "AC6", capacidade_vagas=1)
    ocorrencia_id = _primeira_ocorrencia_id(db, cenario["turma"]["id"])

    aluno_1 = _matricula_ativa(client, db, cenario, "AC6A")
    aluno_2 = _matricula_ativa(client, db, cenario, "AC6B")

    reserva_1 = client.post(
        f"/api/ocorrencias-turma/{ocorrencia_id}/reservas",
        json={"matricula_id": aluno_1["matricula_id"]},
        headers=aluno_1["headers_cliente"],
    )
    assert reserva_1.status_code == 201, reserva_1.text

    reserva_2 = client.post(
        f"/api/ocorrencias-turma/{ocorrencia_id}/reservas",
        json={"matricula_id": aluno_2["matricula_id"]},
        headers=aluno_2["headers_cliente"],
    )
    assert reserva_2.status_code == 409


def test_reserva_avulsa_com_cartao_quando_turma_tem_preco_avulso(client, db):
    cenario = _empresa_com_turma(client, db, "AC7", preco_avulso=60.0)
    ocorrencia_id = _primeira_ocorrencia_id(db, cenario["turma"]["id"])
    cliente = criar_cliente(db, "AC7")
    headers_cliente = auth_header(login(client, cliente["email"], cliente["senha"]))

    resposta = client.post(
        f"/api/ocorrencias-turma/{ocorrencia_id}/reservas",
        json={
            "cliente_nome": "Avulso Teste",
            "cliente_documento": "444.444.444-44",
            "forma_pagamento": "cartao",
            "mp_token": "TOK",
            "mp_payment_method_id": "visa",
        },
        headers=headers_cliente,
    )
    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["tipo_reserva"] == "avulsa"
    assert corpo["preco_pago"] == 60.0
    assert corpo["codigo"]


def test_reserva_avulsa_com_pix_e_rejeitada(client, db):
    cenario = _empresa_com_turma(client, db, "AC8", preco_avulso=60.0)
    ocorrencia_id = _primeira_ocorrencia_id(db, cenario["turma"]["id"])
    cliente = criar_cliente(db, "AC8")
    headers_cliente = auth_header(login(client, cliente["email"], cliente["senha"]))

    resposta = client.post(
        f"/api/ocorrencias-turma/{ocorrencia_id}/reservas",
        json={"cliente_nome": "Avulso Pix", "cliente_documento": "555.555.555-55", "forma_pagamento": "pix"},
        headers=headers_cliente,
    )
    assert resposta.status_code == 400


def test_checkin_academia_sucesso_ja_feito_e_codigo_invalido(client, db):
    cenario = _empresa_com_turma(client, db, "AC9")
    ocorrencia_id = _primeira_ocorrencia_id(db, cenario["turma"]["id"])
    aluno = _matricula_ativa(client, db, cenario, "AC9A")

    reserva = client.post(
        f"/api/ocorrencias-turma/{ocorrencia_id}/reservas",
        json={"matricula_id": aluno["matricula_id"]},
        headers=aluno["headers_cliente"],
    ).json()
    codigo = reserva["codigo"]

    consulta = client.get(f"/api/checkin-academia/{codigo}", headers=cenario["headers_admin"])
    assert consulta.status_code == 200, consulta.text
    assert consulta.json()["checkin_em"] is None

    confirmar = client.post(f"/api/checkin-academia/{codigo}", headers=cenario["headers_admin"])
    assert confirmar.status_code == 200, confirmar.text
    assert confirmar.json()["checkin_em"] is not None

    de_novo = client.post(f"/api/checkin-academia/{codigo}", headers=cenario["headers_admin"])
    assert de_novo.status_code == 409

    invalido = client.get("/api/checkin-academia/ZZZZZZ", headers=cenario["headers_admin"])
    assert invalido.status_code == 404


def test_matricula_inadimplente_pode_reservar_mas_suspensa_nao_pode(client, db):
    from app.models.enums import StatusMatricula

    cenario = _empresa_com_turma(client, db, "AC10", capacidade_vagas=5)
    ocorrencia_id = _primeira_ocorrencia_id(db, cenario["turma"]["id"])
    aluno = _matricula_ativa(client, db, cenario, "AC10A")

    matricula = db.get(Matricula, aluno["matricula_id"])
    matricula.status = StatusMatricula.INADIMPLENTE
    db.commit()

    reserva_inadimplente = client.post(
        f"/api/ocorrencias-turma/{ocorrencia_id}/reservas",
        json={"matricula_id": aluno["matricula_id"]},
        headers=aluno["headers_cliente"],
    )
    assert reserva_inadimplente.status_code == 201, reserva_inadimplente.text

    matricula = db.get(Matricula, aluno["matricula_id"])
    matricula.status = StatusMatricula.SUSPENSA
    db.commit()

    ocorrencia_2 = OcorrenciaTurma(
        tenant_id=matricula.tenant_id,
        turma_id=cenario["turma"]["id"],
        data_hora_inicio=datetime.combine(datetime.utcnow().date() + timedelta(days=7), time(7, 0)),
        data_hora_fim=datetime.combine(datetime.utcnow().date() + timedelta(days=7), time(7, 45)),
        capacidade_vagas=5,
    )
    db.add(ocorrencia_2)
    db.commit()
    db.refresh(ocorrencia_2)

    reserva_suspensa = client.post(
        f"/api/ocorrencias-turma/{ocorrencia_2.id}/reservas",
        json={"matricula_id": aluno["matricula_id"]},
        headers=aluno["headers_cliente"],
    )
    assert reserva_suspensa.status_code == 402


def test_reservar_ocorrencia_no_passado_nao_quebra_com_erro_de_datetime(client, db):
    """Regressão: comparar data_hora_inicio persistida (naive, SQLite
    descarta timezone) contra datetime.utcnow() precisa funcionar sem
    TypeError — mesma classe de bug pega na Fase 2 (Eventos)."""
    cenario = _empresa_com_turma(client, db, "AC11")
    turma = db.get(Turma, cenario["turma"]["id"])

    ocorrencia_passada = OcorrenciaTurma(
        tenant_id=turma.tenant_id,
        turma_id=turma.id,
        data_hora_inicio=datetime.utcnow() - timedelta(days=1),
        data_hora_fim=datetime.utcnow() - timedelta(days=1) + timedelta(minutes=45),
        capacidade_vagas=turma.capacidade_vagas,
    )
    db.add(ocorrencia_passada)
    db.commit()
    db.refresh(ocorrencia_passada)

    aluno = _matricula_ativa(client, db, cenario, "AC11A")
    resposta = client.post(
        f"/api/ocorrencias-turma/{ocorrencia_passada.id}/reservas",
        json={"matricula_id": aluno["matricula_id"]},
        headers=aluno["headers_cliente"],
    )
    assert resposta.status_code == 409
    assert "já aconteceu" in resposta.json()["detail"]


def test_modulo_academia_desligado_bloqueia_criacao_de_turma(client, db):
    empresa = criar_empresa_completa(db, "AC12")
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))

    empresa_db = db.get(Empresa, empresa["empresa_id"])
    empresa_db.academia_ativo = False
    db.commit()

    resposta = client.post(
        "/api/turmas",
        json={
            "nome": "Turma Desligada",
            "dia_semana": 0,
            "hora_inicio": "07:00:00",
            "duracao_minutos": 45,
            "capacidade_vagas": 10,
        },
        headers=headers_admin,
    )
    assert resposta.status_code == 403


def test_isolamento_multi_tenant_entre_empresas(client, db):
    cenario_a = _empresa_com_turma(client, db, "AC13A")
    empresa_b = criar_empresa_completa(db, "AC13B")
    headers_b = auth_header(login(client, empresa_b["admin_email"], empresa_b["senha"]))

    turmas_b = client.get("/api/turmas", headers=headers_b)
    assert turmas_b.status_code == 200
    assert turmas_b.json() == []

    editar_turma_de_outra_empresa = client.patch(
        f"/api/turmas/{cenario_a['turma']['id']}",
        json={"nome": "Hack"},
        headers=headers_b,
    )
    assert editar_turma_de_outra_empresa.status_code == 404

    reservas_de_outra_ocorrencia = client.get(
        f"/api/ocorrencias-turma/{_primeira_ocorrencia_id(db, cenario_a['turma']['id'])}/reservas",
        headers=headers_b,
    )
    assert reservas_de_outra_ocorrencia.status_code == 404


def test_matricula_pela_loja_sem_preco_configurado_e_bloqueada(client, db):
    """Regressão: a rota de autoatendimento nunca deve deixar o cliente
    definir o próprio preço de mensalidade — sem `Empresa.
    preco_padrao_mensalidade_academia` configurado pelo admin, o
    autoatendimento fica bloqueado em vez de aceitar qualquer valor vindo
    do corpo da requisição (que nem existe mais nesse schema)."""
    empresa = criar_empresa_completa(db, "AC14")
    empresa_db = db.get(Empresa, empresa["empresa_id"])
    empresa_db.slug = "academia-ac14"
    db.commit()

    cliente = criar_cliente(db, "AC14")
    headers_cliente = auth_header(login(client, cliente["email"], cliente["senha"]))

    resposta = client.post(
        "/api/matriculas/loja/academia-ac14",
        json={"tipo": "mensal_ilimitado"},
        headers=headers_cliente,
    )
    assert resposta.status_code == 400
    # O schema de autoatendimento nem aceita valor_mensalidade — mesmo que
    # alguém tente mandar, o Pydantic ignora o campo extra.
    resposta_com_preco_forjado = client.post(
        "/api/matriculas/loja/academia-ac14",
        json={"tipo": "mensal_ilimitado", "valor_mensalidade": 0.01},
        headers=headers_cliente,
    )
    assert resposta_com_preco_forjado.status_code == 400


def test_matricula_pela_loja_usa_preco_configurado_pelo_admin(client, db):
    empresa = criar_empresa_completa(db, "AC15")
    headers_admin = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    empresa_db = db.get(Empresa, empresa["empresa_id"])
    empresa_db.slug = "academia-ac15"
    db.commit()

    configurar = client.patch(
        "/api/empresas/minha/academia",
        json={"preco_padrao_mensalidade_academia": 129.9},
        headers=headers_admin,
    )
    assert configurar.status_code == 200, configurar.text

    cliente = criar_cliente(db, "AC15")
    headers_cliente = auth_header(login(client, cliente["email"], cliente["senha"]))

    resposta = client.post(
        "/api/matriculas/loja/academia-ac15",
        # Tenta forjar um preço menor — deve ser ignorado, o servidor usa
        # sempre o preço configurado pelo admin.
        json={"tipo": "mensal_ilimitado", "valor_mensalidade": 1.0},
        headers=headers_cliente,
    )
    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["valor_mensalidade"] == 129.9


def test_staff_matricula_cliente_buscando_email_em_caixa_diferente(client, db):
    """Regressão: staff tentando matricular um aluno pelo e-mail digitado
    em minúsculo levava 'Cliente não encontrado' se a conta do cliente
    tivesse sido criada com alguma letra maiúscula no e-mail — a busca
    comparava o e-mail no banco de forma exata (case-sensitive).

    Cria o cliente direto no banco (não via /auth/registrar-cliente) pra
    não gastar cota do rate limit global desse endpoint, compartilhado
    por toda a sessão de testes (ver tests/helpers.py)."""
    cenario = _empresa_com_turma(client, db, "AC16")

    cliente = Usuario(
        tenant_id=None,
        nome="Aluno Caixa",
        email="Aluno.Caixa@Exemplo.com",
        senha_hash=hash_senha("senha123"),
        role=UserRole.CLIENTE,
        documento="555.555.555-55",
    )
    db.add(cliente)
    db.commit()

    busca = client.get(
        "/api/usuarios/clientes/buscar?email=aluno.caixa@exemplo.com",
        headers=cenario["headers_admin"],
    )
    assert busca.status_code == 200, busca.text
    cliente_id = busca.json()["id"]

    matricular = client.post(
        "/api/matriculas",
        json={"cliente_usuario_id": cliente_id, "tipo": "mensal_ilimitado", "valor_mensalidade": 150.0},
        headers=cenario["headers_admin"],
    )
    assert matricular.status_code == 201, matricular.text
