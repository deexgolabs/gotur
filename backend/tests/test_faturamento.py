from datetime import date, datetime, timedelta

from app.config import settings
from app.models.empresa import Empresa
from app.models.enums import StatusAssinatura, StatusFatura
from app.models.fatura_empresa import FaturaEmpresa
from app.models.plano import Plano
from app.services.faturamento import gerar_faturas_do_dia
from tests.helpers import auth_header, criar_empresa_completa, criar_super_admin, login


def _empresa_com_plano(db, sufixo: str, dias_desde_cadastro: int, preco_mensal: float = 100.0):
    plano = Plano(nome=f"Plano {sufixo}", preco_mensal=preco_mensal)
    db.add(plano)
    db.flush()
    dados = criar_empresa_completa(db, sufixo)
    empresa = db.get(Empresa, dados["empresa_id"])
    empresa.plano_id = plano.id
    empresa.status_assinatura = StatusAssinatura.TRIAL
    empresa.criado_em = datetime.utcnow() - timedelta(days=dias_desde_cadastro)
    db.commit()
    db.refresh(empresa)
    return empresa


def test_empresa_recem_cadastrada_nao_gera_fatura_durante_o_trial(db):
    empresa = _empresa_com_plano(db, "FAT1", dias_desde_cadastro=3)

    geradas = gerar_faturas_do_dia(db)

    assert geradas == []
    assert db.query(FaturaEmpresa).filter(FaturaEmpresa.empresa_id == empresa.id).count() == 0


def test_empresa_com_trial_vencido_gera_primeira_fatura(db):
    empresa = _empresa_com_plano(db, "FAT2", dias_desde_cadastro=settings.trial_dias_gratis + 1, preco_mensal=150.0)

    geradas = gerar_faturas_do_dia(db)

    assert len(geradas) == 1
    assert geradas[0].empresa_id == empresa.id
    assert float(geradas[0].valor) == 150.0
    assert geradas[0].status == StatusFatura.PENDENTE


def test_nao_gera_fatura_duplicada_se_ja_tem_pendente(db):
    empresa = _empresa_com_plano(db, "FAT3", dias_desde_cadastro=settings.trial_dias_gratis + 5)
    db.add(
        FaturaEmpresa(
            empresa_id=empresa.id,
            plano_id=empresa.plano_id,
            valor=100.0,
            status=StatusFatura.PENDENTE,
            vencimento=date.today() + timedelta(days=3),
        )
    )
    db.commit()

    geradas = gerar_faturas_do_dia(db)

    assert geradas == []
    assert db.query(FaturaEmpresa).filter(FaturaEmpresa.empresa_id == empresa.id).count() == 1


def test_gera_nova_fatura_30_dias_apos_vencimento_da_anterior(db):
    empresa = _empresa_com_plano(db, "FAT4", dias_desde_cadastro=100)
    db.add(
        FaturaEmpresa(
            empresa_id=empresa.id,
            plano_id=empresa.plano_id,
            valor=100.0,
            status=StatusFatura.PAGA,
            vencimento=date.today() - timedelta(days=31),
            pago_em=datetime.utcnow() - timedelta(days=31),
        )
    )
    db.commit()

    geradas = gerar_faturas_do_dia(db)

    assert len(geradas) == 1
    assert geradas[0].empresa_id == empresa.id


def test_nao_gera_fatura_antes_dos_30_dias_do_ciclo(db):
    empresa = _empresa_com_plano(db, "FAT5", dias_desde_cadastro=100)
    db.add(
        FaturaEmpresa(
            empresa_id=empresa.id,
            plano_id=empresa.plano_id,
            valor=100.0,
            status=StatusFatura.PAGA,
            vencimento=date.today() - timedelta(days=10),
            pago_em=datetime.utcnow() - timedelta(days=10),
        )
    )
    db.commit()

    geradas = gerar_faturas_do_dia(db)

    assert geradas == []


def test_empresa_sem_plano_nao_gera_fatura(db):
    dados = criar_empresa_completa(db, "FAT6")
    empresa = db.get(Empresa, dados["empresa_id"])
    empresa.criado_em = datetime.utcnow() - timedelta(days=100)
    db.commit()

    geradas = gerar_faturas_do_dia(db)

    assert geradas == []


def test_empresa_cancelada_nao_gera_fatura(db):
    empresa = _empresa_com_plano(db, "FAT7", dias_desde_cadastro=100)
    empresa.status_assinatura = StatusAssinatura.CANCELADA
    db.commit()

    geradas = gerar_faturas_do_dia(db)

    assert geradas == []


def test_empresa_desativada_nao_gera_fatura(db):
    empresa = _empresa_com_plano(db, "FAT8", dias_desde_cadastro=100)
    empresa.ativo = False
    db.commit()

    geradas = gerar_faturas_do_dia(db)

    assert geradas == []


def test_empresa_isenta_de_cobranca_nao_gera_fatura(db):
    empresa = _empresa_com_plano(db, "FAT9", dias_desde_cadastro=100)
    empresa.isento_cobranca = True
    db.commit()

    geradas = gerar_faturas_do_dia(db)

    assert geradas == []
    assert db.query(FaturaEmpresa).filter(FaturaEmpresa.empresa_id == empresa.id).count() == 0


def test_super_admin_isenta_empresa_de_cobranca(client, db):
    super_admin = criar_super_admin(db, "FATISN1")
    headers = auth_header(login(client, super_admin["email"], super_admin["senha"]))
    dados = criar_empresa_completa(db, "FATISN1")

    resposta = client.patch(
        f"/api/empresas/{dados['empresa_id']}/isencao-cobranca",
        json={"isento_cobranca": True},
        headers=headers,
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["isento_cobranca"] is True

    empresa = db.get(Empresa, dados["empresa_id"])
    assert empresa.isento_cobranca is True


def test_super_admin_volta_a_cobrar_empresa_isenta(client, db):
    super_admin = criar_super_admin(db, "FATISN2")
    headers = auth_header(login(client, super_admin["email"], super_admin["senha"]))
    dados = criar_empresa_completa(db, "FATISN2")
    empresa = db.get(Empresa, dados["empresa_id"])
    empresa.isento_cobranca = True
    db.commit()

    resposta = client.patch(
        f"/api/empresas/{dados['empresa_id']}/isencao-cobranca",
        json={"isento_cobranca": False},
        headers=headers,
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["isento_cobranca"] is False


def test_admin_empresa_nao_pode_se_isentar_de_cobranca(client, db):
    dados = criar_empresa_completa(db, "FATISN3")
    headers = auth_header(login(client, dados["admin_email"], dados["senha"]))

    resposta = client.patch(
        f"/api/empresas/{dados['empresa_id']}/isencao-cobranca",
        json={"isento_cobranca": True},
        headers=headers,
    )

    assert resposta.status_code == 403
