from datetime import date, datetime, timedelta

from app.database import SessionLocal
from app.models.empresa import Empresa
from app.models.enums import StatusAssinatura
from app.models.fatura_empresa import FaturaEmpresa
from app.models.usuario import Usuario
from tests.helpers import auth_header, criar_cliente, criar_empresa_completa, criar_super_admin, login


def _criar_plano(client, headers, **kwargs):
    dados = {
        "nome": "Basico",
        "preco_mensal": 99.9,
        "max_onibus": 1,
        "max_funcionarios": 2,
        "max_viagens_mes": 1,
    }
    dados.update(kwargs)
    resposta = client.post("/api/planos", json=dados, headers=headers)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _empresa_com_plano(client, db, sufixo: str, **limites):
    super_admin = criar_super_admin(db, sufixo)
    token_super = login(client, super_admin["email"], super_admin["senha"])
    headers_super = auth_header(token_super)
    plano = _criar_plano(client, headers_super, **limites)

    empresa = criar_empresa_completa(db, sufixo)
    db_empresa = db.get(Empresa, empresa["empresa_id"])
    db_empresa.plano_id = plano["id"]
    db.commit()

    return empresa, plano, headers_super


def test_limite_de_onibus_do_plano_bloqueia_criacao_extra(client, db):
    empresa, _plano, _headers_super = _empresa_com_plano(client, db, "P1", max_onibus=1)
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    # criar_empresa_completa já criou 1 ônibus -> limite já atingido
    resposta = client.post(
        "/api/onibus",
        json={"identificacao": "BUS-EXTRA", "tipo": "convencional", "total_poltronas": 4},
        headers=headers,
    )
    assert resposta.status_code == 402


def test_limite_de_funcionarios_do_plano_bloqueia_criacao_extra(client, db):
    empresa, _plano, _headers_super = _empresa_com_plano(client, db, "P2", max_funcionarios=2)
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    # criar_empresa_completa já criou admin + funcionário -> limite (2) já atingido
    resposta = client.post(
        "/api/usuarios/funcionarios",
        json={"nome": "Extra", "email": "extra.func@teste.com", "senha": "123456"},
        headers=headers,
    )
    assert resposta.status_code == 402


def test_empresa_sem_plano_nao_tem_limite(client, db):
    empresa = criar_empresa_completa(db, "P3")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    resposta = client.post(
        "/api/onibus",
        json={"identificacao": "BUS-LIVRE", "tipo": "convencional", "total_poltronas": 4},
        headers=headers,
    )
    assert resposta.status_code == 201


def test_gerar_fatura_pagar_e_reativar_assinatura(client, db):
    empresa, _plano, headers_super = _empresa_com_plano(client, db, "P4")

    resposta = client.post(f"/api/empresas/{empresa['empresa_id']}/faturas", headers=headers_super)
    assert resposta.status_code == 201, resposta.text
    fatura_id = resposta.json()["id"]
    assert resposta.json()["status"] == "pendente"

    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)
    pagar = client.post(f"/api/faturas/{fatura_id}/pagar", headers=headers)
    assert pagar.status_code == 200
    assert pagar.json()["status"] == "pendente"
    assert pagar.json()["pix_copia_cola"]

    confirmar = client.post(f"/api/faturas/{fatura_id}/confirmar-simulado", headers=headers)
    assert confirmar.status_code == 200
    assert confirmar.json()["status"] == "paga"


def test_empresa_suspensa_bloqueia_operacao_mas_nao_o_pagamento_da_fatura(client, db):
    empresa, plano, headers_super = _empresa_com_plano(client, db, "P5")

    # Fatura vencida há mais que a tolerância -> deve suspender ao consultar.
    fatura = FaturaEmpresa(
        empresa_id=empresa["empresa_id"],
        plano_id=plano["id"],
        valor=plano["preco_mensal"],
        vencimento=date.today() - timedelta(days=15),
    )
    db.add(fatura)
    db.commit()
    db.refresh(fatura)

    # Duas chamadas: a checagem preguiçosa converge em até 2 passadas
    # (ativa->inadimplente->suspensa), mesmo padrão da expiração de hold.
    client.get("/api/empresas", headers=headers_super)
    client.get("/api/empresas", headers=headers_super)

    db.refresh(db.get(Empresa, empresa["empresa_id"]))
    empresa_db = db.get(Empresa, empresa["empresa_id"])
    assert empresa_db.status_assinatura == StatusAssinatura.SUSPENSA

    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    bloqueado = client.post(
        "/api/rotas",
        json={"origem": "X", "destino": "Y"},
        headers=headers,
    )
    assert bloqueado.status_code == 402

    minhas_faturas = client.get("/api/faturas/minhas", headers=headers)
    assert minhas_faturas.status_code == 200

    pagar = client.post(f"/api/faturas/{fatura.id}/pagar", headers=headers)
    assert pagar.status_code == 200
    assert pagar.json()["status"] == "pendente"

    confirmar = client.post(f"/api/faturas/{fatura.id}/confirmar-simulado", headers=headers)
    assert confirmar.status_code == 200
    assert confirmar.json()["status"] == "paga"

    liberado = client.post(
        "/api/rotas",
        json={"origem": "X", "destino": "Y"},
        headers=headers,
    )
    assert liberado.status_code == 201


def test_cadastro_publico_de_empresa_cria_admin_logado(client, db):
    super_admin = criar_super_admin(db, "P6")
    token_super = login(client, super_admin["email"], super_admin["senha"])
    plano = _criar_plano(client, auth_header(token_super))

    resposta = client.post(
        "/api/auth/registrar-empresa",
        json={
            "empresa_nome": "Viação Onboarding Teste",
            "cnpj": "99.999.999/0001-99",
            "plano_id": plano["id"],
            "admin_nome": "Dono",
            "admin_email": "dono.onboarding@teste.com",
            "admin_senha": "senha123",
        },
    )
    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["role"] == "admin_empresa"
    assert corpo["access_token"]


def test_criar_plano_sem_modulo_frete_persiste_desligado(client, db):
    super_admin = criar_super_admin(db, "P7")
    headers = auth_header(login(client, super_admin["email"], super_admin["senha"]))

    plano = _criar_plano(client, headers, nome="Só Passagem", modulo_frete=False)
    assert plano["modulo_frete"] is False

    lista = client.get("/api/planos", headers=headers).json()
    encontrado = next(p for p in lista if p["id"] == plano["id"])
    assert encontrado["modulo_frete"] is False


def test_editar_plano_liga_e_desliga_modulo_frete(client, db):
    super_admin = criar_super_admin(db, "P8")
    headers = auth_header(login(client, super_admin["email"], super_admin["senha"]))
    plano = _criar_plano(client, headers, modulo_frete=True)

    desligado = client.patch(f"/api/planos/{plano['id']}", json={"modulo_frete": False}, headers=headers)
    assert desligado.status_code == 200, desligado.text
    assert desligado.json()["modulo_frete"] is False

    religado = client.patch(f"/api/planos/{plano['id']}", json={"modulo_frete": True}, headers=headers)
    assert religado.status_code == 200
    assert religado.json()["modulo_frete"] is True


def test_criar_e_editar_plano_liga_e_desliga_modulo_eventos_e_academia(client, db):
    """Regressão: modulo_eventos/modulo_academia existem na coluna do
    Plano desde a Fase 2/3, mas modulo_academia ficou de fora do schema
    (PlanoCreate/Update/Out) até esse teste ser escrito — a API aceitava
    o campo silenciosamente sem persistir nada. Cobre os dois módulos
    dos nichos novos (não-aviação) do mesmo jeito que já se cobre frete."""
    super_admin = criar_super_admin(db, "P10")
    headers = auth_header(login(client, super_admin["email"], super_admin["senha"]))

    plano = _criar_plano(client, headers, nome="Cinema e Academia", modulo_eventos=False, modulo_academia=False)
    assert plano["modulo_eventos"] is False
    assert plano["modulo_academia"] is False

    lista = client.get("/api/planos", headers=headers).json()
    encontrado = next(p for p in lista if p["id"] == plano["id"])
    assert encontrado["modulo_eventos"] is False
    assert encontrado["modulo_academia"] is False

    religado = client.patch(
        f"/api/planos/{plano['id']}", json={"modulo_eventos": True, "modulo_academia": True}, headers=headers
    )
    assert religado.status_code == 200, religado.text
    assert religado.json()["modulo_eventos"] is True
    assert religado.json()["modulo_academia"] is True


def test_editar_detalhes_do_plano(client, db):
    super_admin = criar_super_admin(db, "P9")
    headers = auth_header(login(client, super_admin["email"], super_admin["senha"]))
    plano = _criar_plano(client, headers)

    resposta = client.patch(
        f"/api/planos/{plano['id']}",
        json={
            "nome": "Plano Renomeado",
            "descricao": "Nova descrição",
            "preco_mensal": 149.9,
            "max_onibus": 3,
            "max_funcionarios": 5,
            "max_viagens_mes": 10,
        },
        headers=headers,
    )
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["nome"] == "Plano Renomeado"
    assert corpo["descricao"] == "Nova descrição"
    assert corpo["preco_mensal"] == 149.9
    assert corpo["max_onibus"] == 3
    assert corpo["max_funcionarios"] == 5
    assert corpo["max_viagens_mes"] == 10


def test_limite_de_locais_do_plano_bloqueia_criacao_extra(client, db):
    """Equivalente de test_limite_de_onibus_do_plano_bloqueia_criacao_extra
    pro nicho de eventos — locais são pro eventos o que ônibus é pra
    viação (ver app/services/limites_plano.py)."""
    empresa, _plano, _headers_super = _empresa_com_plano(client, db, "P11", max_locais=1)
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    # _empresa_com_plano já não cria local nenhum, então o primeiro deve passar.
    primeiro = client.post(
        "/api/locais",
        json={"nome": "Teatro Principal", "total_assentos": 4},
        headers=headers,
    )
    assert primeiro.status_code == 201, primeiro.text

    segundo = client.post(
        "/api/locais",
        json={"nome": "Teatro Extra", "total_assentos": 4},
        headers=headers,
    )
    assert segundo.status_code == 402


def test_limite_de_sessoes_mes_do_plano_bloqueia_criacao_extra(client, db):
    empresa, _plano, _headers_super = _empresa_com_plano(client, db, "P12", max_sessoes_mes=1)
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    local = client.post(
        "/api/locais",
        json={"nome": "Teatro P12", "total_assentos": 4},
        headers=headers,
    )
    assert local.status_code == 201, local.text
    local_id = local.json()["id"]

    def _criar_sessao():
        return client.post(
            "/api/sessoes",
            json={
                "local_id": local_id,
                "nome_evento": "Show",
                "data_hora": (datetime.now() + timedelta(days=5)).isoformat(),
                "preco": 100.0,
            },
            headers=headers,
        )

    primeira = _criar_sessao()
    assert primeira.status_code == 201, primeira.text

    segunda = _criar_sessao()
    assert segunda.status_code == 402


def test_limite_de_turmas_do_plano_bloqueia_criacao_extra(client, db):
    empresa, _plano, _headers_super = _empresa_com_plano(client, db, "P13", max_turmas=1)
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    def _criar_turma(nome):
        return client.post(
            "/api/turmas",
            json={
                "nome": nome,
                "dia_semana": 1,
                "hora_inicio": "10:00:00",
                "duracao_minutos": 45,
                "capacidade_vagas": 10,
            },
            headers=headers,
        )

    primeira = _criar_turma("Turma 1")
    assert primeira.status_code == 201, primeira.text

    segunda = _criar_turma("Turma 2")
    assert segunda.status_code == 402


def test_limite_de_matriculas_ativas_do_plano_bloqueia_criacao_extra(client, db):
    empresa, _plano, _headers_super = _empresa_com_plano(client, db, "P14", max_matriculas_ativas=1)
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    cliente = criar_cliente(db, "P14")
    cliente_usuario_id = db.query(Usuario).filter(Usuario.email == cliente["email"]).first().id

    def _matricular():
        return client.post(
            "/api/matriculas",
            json={"cliente_usuario_id": cliente_usuario_id, "tipo": "mensal_ilimitado", "valor_mensalidade": 100.0},
            headers=headers,
        )

    primeira = _matricular()
    assert primeira.status_code == 201, primeira.text

    segunda = _matricular()
    assert segunda.status_code == 402
