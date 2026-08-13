from datetime import date, timedelta

from app.models.empresa import Empresa
from app.models.enums import StatusAssinatura, StatusFatura
from app.models.fatura_empresa import FaturaEmpresa
from app.models.plano import Plano
from app.services.assinatura import atualizar_situacao_assinaturas
from tests.helpers import criar_empresa_completa


def _empresa_com_fatura_vencida(db, sufixo: str, dias_atraso: int, status_assinatura: StatusAssinatura):
    plano = Plano(nome=f"Plano {sufixo}", preco_mensal=100.0)
    db.add(plano)
    db.flush()
    dados = criar_empresa_completa(db, sufixo)
    empresa = db.get(Empresa, dados["empresa_id"])
    empresa.plano_id = plano.id
    empresa.status_assinatura = status_assinatura
    db.add(
        FaturaEmpresa(
            empresa_id=empresa.id,
            plano_id=plano.id,
            valor=100.0,
            status=StatusFatura.PENDENTE,
            vencimento=date.today() - timedelta(days=dias_atraso),
        )
    )
    db.commit()
    db.refresh(empresa)
    return empresa


def test_empresa_com_fatura_vencida_vira_inadimplente(db):
    empresa = _empresa_com_fatura_vencida(db, "ASS1", dias_atraso=1, status_assinatura=StatusAssinatura.ATIVA)

    atualizar_situacao_assinaturas(db)
    db.refresh(empresa)

    assert empresa.status_assinatura == StatusAssinatura.INADIMPLENTE


def test_empresa_inadimplente_ha_muito_tempo_e_suspensa(db):
    empresa = _empresa_com_fatura_vencida(db, "ASS2", dias_atraso=15, status_assinatura=StatusAssinatura.INADIMPLENTE)

    atualizar_situacao_assinaturas(db)
    db.refresh(empresa)

    assert empresa.status_assinatura == StatusAssinatura.SUSPENSA


def test_empresa_isenta_nao_vira_inadimplente_mesmo_com_fatura_vencida(db):
    empresa = _empresa_com_fatura_vencida(db, "ASS3", dias_atraso=1, status_assinatura=StatusAssinatura.ATIVA)
    empresa.isento_cobranca = True
    db.commit()

    atualizar_situacao_assinaturas(db)
    db.refresh(empresa)

    assert empresa.status_assinatura == StatusAssinatura.ATIVA


def test_empresa_isenta_nao_e_suspensa_mesmo_ja_inadimplente_ha_muito_tempo(db):
    """Cobre o caso de uma empresa que já estava inadimplente antes de
    virar isenta — a isenção precisa proteger contra a suspensão mesmo
    assim, não só contra virar inadimplente pela primeira vez."""
    empresa = _empresa_com_fatura_vencida(db, "ASS4", dias_atraso=15, status_assinatura=StatusAssinatura.INADIMPLENTE)
    empresa.isento_cobranca = True
    db.commit()

    atualizar_situacao_assinaturas(db)
    db.refresh(empresa)

    assert empresa.status_assinatura == StatusAssinatura.INADIMPLENTE
