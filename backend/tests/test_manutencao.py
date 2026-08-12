from datetime import date, timedelta

from app.services.manutencao import verificar_documentos_vencendo
from tests.helpers import auth_header, criar_empresa_completa, login


def _criar_documento(client, headers, onibus_id, dias_para_vencer, tipo="crlv"):
    vencimento = (date.today() + timedelta(days=dias_para_vencer)).isoformat()
    resposta = client.post(
        f"/api/onibus/{onibus_id}/documentos",
        json={"tipo": tipo, "data_vencimento": vencimento},
        headers=headers,
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_notifica_apenas_empresas_com_documento_vencendo_na_janela(client, db):
    empresa_perto = criar_empresa_completa(db, "MANUT1")
    empresa_longe = criar_empresa_completa(db, "MANUT2")
    empresa_sem_doc = criar_empresa_completa(db, "MANUT3")

    headers_perto = auth_header(login(client, empresa_perto["admin_email"], empresa_perto["senha"]))
    headers_longe = auth_header(login(client, empresa_longe["admin_email"], empresa_longe["senha"]))

    _criar_documento(client, headers_perto, empresa_perto["onibus_id"], dias_para_vencer=10)
    _criar_documento(client, headers_longe, empresa_longe["onibus_id"], dias_para_vencer=60)

    total_notificado = verificar_documentos_vencendo(db, dias_alerta=15)
    assert total_notificado == 1


def test_documento_ja_vencido_nao_gera_alerta_repetido(client, db):
    """A janela é só pra frente (hoje até N dias) — documento já vencido há
    muito tempo não entra no alerta diário indefinidamente."""
    empresa = criar_empresa_completa(db, "MANUT4")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    _criar_documento(client, headers, empresa["onibus_id"], dias_para_vencer=-30)

    total_notificado = verificar_documentos_vencendo(db, dias_alerta=15)
    assert total_notificado == 0


def test_documento_vencendo_hoje_entra_no_alerta(client, db):
    empresa = criar_empresa_completa(db, "MANUT5")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    _criar_documento(client, headers, empresa["onibus_id"], dias_para_vencer=0)

    total_notificado = verificar_documentos_vencendo(db, dias_alerta=15)
    assert total_notificado == 1


def test_agrupa_varios_documentos_da_mesma_empresa_num_unico_alerta(client, db):
    empresa = criar_empresa_completa(db, "MANUT6")
    headers = auth_header(login(client, empresa["admin_email"], empresa["senha"]))
    _criar_documento(client, headers, empresa["onibus_id"], dias_para_vencer=5, tipo="crlv")
    _criar_documento(client, headers, empresa["onibus_id"], dias_para_vencer=8, tipo="seguro")

    total_notificado = verificar_documentos_vencendo(db, dias_alerta=15)
    assert total_notificado == 1
