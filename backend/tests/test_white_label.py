import io
from datetime import datetime, timedelta

from PIL import Image

from tests.helpers import auth_header, criar_empresa_completa, login


def _imagem_png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (300, 300), (255, 0, 0, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_empresa_ganha_slug_automatico_ao_acessar_minha_empresa(client, db):
    empresa = criar_empresa_completa(db, "WL1")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    resposta = client.get("/api/empresas/minha", headers=headers)
    assert resposta.status_code == 200
    slug = resposta.json()["slug"]
    assert slug
    assert " " not in slug


def test_configurar_slug_e_cor_e_loja_publica_reflete(client, db):
    empresa = criar_empresa_completa(db, "WL2")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    resposta = client.patch(
        "/api/empresas/minha/marca", json={"slug": "Viacao Teste!!", "cor_primaria": "#ff0000"}, headers=headers
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["slug"] == "viacao-teste"
    assert corpo["cor_primaria"] == "#ff0000"

    publico = client.get(f"/api/empresas/loja/{corpo['slug']}")
    assert publico.status_code == 200
    assert publico.json()["cor_primaria"] == "#ff0000"
    assert publico.json()["id"] == empresa["empresa_id"]


def test_configurar_dados_da_empresa_e_textos_da_loja(client, db):
    empresa = criar_empresa_completa(db, "WLDADOS")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    resposta = client.patch(
        "/api/empresas/minha/dados",
        json={
            "nome": "Viação Renomeada",
            "telefone_contato": "(63) 99999-8888",
            "email_contato": "contato@renomeada.com",
            "texto_loja": "Atendimento de seg a sáb, 8h às 18h.",
        },
        headers=headers,
    )
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["nome"] == "Viação Renomeada"
    assert corpo["telefone_contato"] == "(63) 99999-8888"
    assert corpo["texto_loja"] == "Atendimento de seg a sáb, 8h às 18h."

    slug = client.patch("/api/empresas/minha/marca", json={"slug": "loja-wldados"}, headers=headers).json()["slug"]
    publico = client.get(f"/api/empresas/loja/{slug}")
    assert publico.status_code == 200
    assert publico.json()["telefone_contato"] == "(63) 99999-8888"
    assert publico.json()["texto_loja"] == "Atendimento de seg a sáb, 8h às 18h."


def test_slug_duplicado_e_rejeitado(client, db):
    empresa_a = criar_empresa_completa(db, "WL3")
    empresa_b = criar_empresa_completa(db, "WL4")
    token_a = login(client, empresa_a["admin_email"], empresa_a["senha"])
    token_b = login(client, empresa_b["admin_email"], empresa_b["senha"])

    ok = client.patch("/api/empresas/minha/marca", json={"slug": "mesmo-nome"}, headers=auth_header(token_a))
    assert ok.status_code == 200

    conflito = client.patch("/api/empresas/minha/marca", json={"slug": "mesmo-nome"}, headers=auth_header(token_b))
    assert conflito.status_code == 409


def test_upload_de_logo_gera_icones_e_url(client, db):
    empresa = criar_empresa_completa(db, "WL5")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)

    resposta = client.post(
        "/api/empresas/minha/logo",
        files={"arquivo": ("logo.png", _imagem_png_bytes(), "image/png")},
        headers=headers,
    )
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["logo_url"] is not None
    assert "/media/empresas/" in corpo["logo_url"]


def test_loja_404_para_slug_inexistente(client, db):
    resposta = client.get("/api/empresas/loja/nao-existe-123")
    assert resposta.status_code == 404


def test_pagina_e_manifest_da_loja(client, db):
    empresa = criar_empresa_completa(db, "WL6")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)
    slug = client.patch("/api/empresas/minha/marca", json={"slug": "loja-wl6", "cor_primaria": "#123456"}, headers=headers).json()["slug"]

    pagina = client.get(f"/loja/{slug}")
    assert pagina.status_code == 200
    assert "text/html" in pagina.headers["content-type"]

    manifesto = client.get(f"/loja/{slug}/manifest.json")
    assert manifesto.status_code == 200
    corpo = manifesto.json()
    assert corpo["theme_color"] == "#123456"
    assert corpo["start_url"] == f"/loja/{slug}"

    sw = client.get(f"/loja/{slug}/service-worker.js")
    assert sw.status_code == 200

    inexistente = client.get("/loja/nao-existe-123")
    assert inexistente.status_code == 404


def test_landing_page_de_evento_e_aula_servem_o_mesmo_shell_da_loja(client, db):
    """Links diretos compartilháveis (ex: divulgação de um show ou aula
    específica) servem o mesmo HTML da SPA — é o frontend que lê a URL e
    abre direto no item certo."""
    empresa = criar_empresa_completa(db, "WL9")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)
    slug = client.patch("/api/empresas/minha/marca", json={"slug": "loja-wl9"}, headers=headers).json()["slug"]

    pagina_evento = client.get(f"/loja/{slug}/eventos/999")
    assert pagina_evento.status_code == 200
    assert "text/html" in pagina_evento.headers["content-type"]

    pagina_aula = client.get(f"/loja/{slug}/aulas/999")
    assert pagina_aula.status_code == 200
    assert "text/html" in pagina_aula.headers["content-type"]

    assert client.get("/loja/nao-existe-123/eventos/1").status_code == 404
    assert client.get("/loja/nao-existe-123/aulas/1").status_code == 404


def test_busca_de_viagens_filtrada_por_tenant(client, db):
    empresa_a = criar_empresa_completa(db, "WL7")
    empresa_b = criar_empresa_completa(db, "WL8")

    # Usa a data da própria viagem criada por criar_empresa_completa (amanhã).
    data_str = (datetime.now() + timedelta(days=1)).date().isoformat()

    resultado_a = client.get(
        f"/api/viagens/buscar?origem=OrigemWL7&destino=DestinoWL7&data={data_str}&tenant_id={empresa_a['empresa_id']}"
    )
    assert resultado_a.status_code == 200
    assert len(resultado_a.json()) == 1

    resultado_b = client.get(
        f"/api/viagens/buscar?origem=OrigemWL7&destino=DestinoWL7&data={data_str}&tenant_id={empresa_b['empresa_id']}"
    )
    assert resultado_b.status_code == 200
    assert len(resultado_b.json()) == 0


def test_solicitar_orcamento_fretamento_pela_loja(client, db):
    empresa = criar_empresa_completa(db, "WL9")
    token = login(client, empresa["admin_email"], empresa["senha"])
    headers = auth_header(token)
    slug = client.patch("/api/empresas/minha/marca", json={"slug": "loja-wl9"}, headers=headers).json()["slug"]

    resposta = client.post(
        f"/api/fretamentos/loja/{slug}/solicitar",
        json={
            "cliente_nome": "Turma da Escola",
            "cliente_contato": "(11) 99999-0000",
            "origem": "Escola X",
            "destino": "Praia Y",
            "data_hora_saida": "2026-10-01T06:00:00",
        },
    )
    assert resposta.status_code == 201, resposta.text
    codigo = resposta.json()["codigo_rastreio"]

    lista = client.get("/api/fretamentos", headers=headers)
    assert any(f["codigo_rastreio"] == codigo for f in lista.json())

    invalido = client.post(
        "/api/fretamentos/loja/slug-inexistente/solicitar",
        json={
            "cliente_nome": "X",
            "cliente_contato": "X",
            "origem": "A",
            "destino": "B",
            "data_hora_saida": "2026-10-01T06:00:00",
        },
    )
    assert invalido.status_code == 404


def test_loja_publica_expoe_public_key_do_mercadopago_quando_automatica(client, db):
    empresa = criar_empresa_completa(db, "WL10")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    marca = client.patch("/api/empresas/minha/marca", json={"slug": "viacao-wl10"}, headers=headers).json()
    client.patch(
        "/api/empresas/minha/pagamento",
        json={"mercadopago_access_token": "TOKEN-X", "mercadopago_public_key": "PUBLIC-KEY-X"},
        headers=headers,
    )

    publico = client.get(f"/api/empresas/loja/{marca['slug']}")
    assert publico.status_code == 200
    assert publico.json()["mercadopago_public_key"] == "PUBLIC-KEY-X"


def test_loja_publica_esconde_public_key_quando_modo_nao_e_automatica(client, db):
    empresa = criar_empresa_completa(db, "WL11")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    marca = client.patch("/api/empresas/minha/marca", json={"slug": "viacao-wl11"}, headers=headers).json()
    client.patch(
        "/api/empresas/minha/pagamento",
        json={"mercadopago_access_token": "TOKEN-X", "mercadopago_public_key": "PUBLIC-KEY-X", "modo_cobranca": "manual"},
        headers=headers,
    )

    publico = client.get(f"/api/empresas/loja/{marca['slug']}")
    assert publico.status_code == 200
    assert publico.json()["mercadopago_public_key"] is None
