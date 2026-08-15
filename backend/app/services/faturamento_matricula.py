"""Cobrança recorrente da mensalidade de aluno de academia — mesma receita
de app/services/faturamento.py (FaturaEmpresa), mas escopada em Matricula.
A primeira fatura de uma matrícula nasce na hora da assinatura (ver
app/routers/matriculas.py), não aqui: esta função só gera as renovações
(ciclo 2, 3...), sempre `CICLO_DIAS` depois do vencimento anterior — não
depende de quando foi paga, pra não empurrar o ciclo pra frente
indefinidamente se o aluno atrasar. Matrícula com fatura pendente em
aberto não recebe uma nova (evita cobrança duplicada)."""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.academia import FaturaMatricula, Matricula
from app.models.enums import StatusFatura, StatusMatricula

CICLO_DIAS = 30
DIAS_PARA_VENCIMENTO = 7


def gerar_faturas_matricula_do_dia(db: Session) -> list[FaturaMatricula]:
    hoje = date.today()
    geradas: list[FaturaMatricula] = []

    matriculas = (
        db.query(Matricula)
        .filter(Matricula.status.in_([StatusMatricula.ATIVA, StatusMatricula.INADIMPLENTE]))
        .all()
    )

    for matricula in matriculas:
        tem_pendente = (
            db.query(FaturaMatricula)
            .filter(FaturaMatricula.matricula_id == matricula.id, FaturaMatricula.status == StatusFatura.PENDENTE)
            .first()
        )
        if tem_pendente:
            continue

        ultima_fatura = (
            db.query(FaturaMatricula)
            .filter(FaturaMatricula.matricula_id == matricula.id)
            .order_by(FaturaMatricula.vencimento.desc())
            .first()
        )
        if not ultima_fatura:
            # Não deveria acontecer (a 1ª fatura nasce na assinatura), mas
            # sem fatura anterior não há ciclo pra calcular a próxima — pula.
            continue
        if ultima_fatura.vencimento + timedelta(days=CICLO_DIAS) > hoje:
            continue

        fatura = FaturaMatricula(
            tenant_id=matricula.tenant_id,
            matricula_id=matricula.id,
            cliente_usuario_id=matricula.cliente_usuario_id,
            valor=matricula.valor_mensalidade,
            status=StatusFatura.PENDENTE,
            vencimento=hoje + timedelta(days=DIAS_PARA_VENCIMENTO),
        )
        db.add(fatura)
        db.commit()
        db.refresh(fatura)
        geradas.append(fatura)

    return geradas
