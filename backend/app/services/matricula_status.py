"""Situação da matrícula de um aluno de academia: marca fatura vencida
como motivo de inadimplência, e suspende matrículas inadimplentes há
tempo demais. Checagem "preguiçosa" (roda quando alguém consulta as
próprias matrículas), mesmo espírito de app/services/assinatura.py — não
depende de um cron externo, embora um cron diário seja o ideal em produção
(ver scripts/gerar_faturas_matricula.py)."""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.academia import FaturaMatricula, Matricula
from app.models.enums import StatusFatura, StatusMatricula

DIAS_TOLERANCIA_ANTES_DE_SUSPENDER = 5


def atualizar_situacao_matriculas(db: Session) -> None:
    hoje = date.today()
    alterou = False

    faturas_vencidas = (
        db.query(FaturaMatricula)
        .filter(FaturaMatricula.status == StatusFatura.PENDENTE, FaturaMatricula.vencimento < hoje)
        .all()
    )
    matriculas_com_atraso: set[int] = {f.matricula_id for f in faturas_vencidas}

    for matricula_id in matriculas_com_atraso:
        matricula = db.get(Matricula, matricula_id)
        if not matricula or matricula.status != StatusMatricula.ATIVA:
            continue
        matricula.status = StatusMatricula.INADIMPLENTE
        alterou = True

    # Suspende quem está inadimplente há mais que a tolerância.
    limite = hoje - timedelta(days=DIAS_TOLERANCIA_ANTES_DE_SUSPENDER)
    inadimplentes = db.query(Matricula).filter(Matricula.status == StatusMatricula.INADIMPLENTE).all()
    for matricula in inadimplentes:
        fatura_mais_antiga_vencida = (
            db.query(FaturaMatricula)
            .filter(
                FaturaMatricula.matricula_id == matricula.id,
                FaturaMatricula.status == StatusFatura.PENDENTE,
                FaturaMatricula.vencimento < hoje,
            )
            .order_by(FaturaMatricula.vencimento.asc())
            .first()
        )
        if fatura_mais_antiga_vencida and fatura_mais_antiga_vencida.vencimento < limite:
            matricula.status = StatusMatricula.SUSPENSA
            alterou = True

    if alterou:
        db.commit()
