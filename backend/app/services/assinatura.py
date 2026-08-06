"""Situação da assinatura da empresa na plataforma: marca fatura vencida
como motivo de inadimplência, e suspende empresas inadimplentes há tempo
demais. Checagem "preguiçosa" (roda quando alguém consulta faturas/lista de
empresas), no mesmo espírito da expiração de hold de poltrona — não
depende de um cron externo, embora um cron diário seja o ideal em produção
com volume real (ver DEPLOY.md)."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.empresa import Empresa
from app.models.enums import StatusAssinatura, StatusFatura
from app.models.fatura_empresa import FaturaEmpresa

DIAS_TOLERANCIA_ANTES_DE_SUSPENDER = 10


def atualizar_situacao_assinaturas(db: Session) -> None:
    hoje = date.today()
    alterou = False

    faturas_vencidas = (
        db.query(FaturaEmpresa)
        .filter(FaturaEmpresa.status == StatusFatura.PENDENTE, FaturaEmpresa.vencimento < hoje)
        .all()
    )
    empresas_com_atraso: set[int] = {f.empresa_id for f in faturas_vencidas}

    for empresa_id in empresas_com_atraso:
        empresa = db.get(Empresa, empresa_id)
        if not empresa or empresa.status_assinatura not in (StatusAssinatura.ATIVA, StatusAssinatura.TRIAL):
            continue
        empresa.status_assinatura = StatusAssinatura.INADIMPLENTE
        alterou = True

    # Suspende quem está inadimplente há mais que a tolerância.
    limite = hoje - timedelta(days=DIAS_TOLERANCIA_ANTES_DE_SUSPENDER)
    inadimplentes = db.query(Empresa).filter(Empresa.status_assinatura == StatusAssinatura.INADIMPLENTE).all()
    for empresa in inadimplentes:
        fatura_mais_antiga_vencida = (
            db.query(FaturaEmpresa)
            .filter(
                FaturaEmpresa.empresa_id == empresa.id,
                FaturaEmpresa.status == StatusFatura.PENDENTE,
                FaturaEmpresa.vencimento < hoje,
            )
            .order_by(FaturaEmpresa.vencimento.asc())
            .first()
        )
        if fatura_mais_antiga_vencida and fatura_mais_antiga_vencida.vencimento < limite:
            empresa.status_assinatura = StatusAssinatura.SUSPENSA
            alterou = True

    if alterou:
        db.commit()
