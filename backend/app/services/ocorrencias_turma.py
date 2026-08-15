"""Gera as instâncias datadas (OcorrenciaTurma) de uma Turma recorrente,
mantendo sempre uma janela rolante de `SEMANAS_JANELA` semanas à frente.
Idempotente por construção: sempre continua a partir da última ocorrência
já gerada (ou de hoje, se a Turma é nova), então rodar de novo sobre uma
janela já preenchida não cria nada — só estende o que falta."""

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.academia import OcorrenciaTurma, Turma

SEMANAS_JANELA = 8


def _proxima_data_para_dia_semana(a_partir_de: date, dia_semana: int) -> date:
    dias_ate = (dia_semana - a_partir_de.weekday()) % 7
    return a_partir_de + timedelta(days=dias_ate)


def gerar_ocorrencias(db: Session, turma: Turma, ate_data: date | None = None) -> list[OcorrenciaTurma]:
    """`ate_data`/"hoje" usam `datetime.utcnow().date()`, não
    `date.today()` (hora local do servidor) — data_hora_inicio é
    comparado contra `datetime.utcnow()` em outros lugares (ex:
    reservas_aula.py), então misturar data local com hora UTC faria uma
    ocorrência recém-criada parecer "no passado" sempre que o fuso local
    do servidor estiver adiantado em relação ao UTC."""
    hoje_utc = datetime.utcnow().date()
    ate_data = ate_data or hoje_utc + timedelta(weeks=SEMANAS_JANELA)

    ultima = (
        db.query(OcorrenciaTurma)
        .filter(OcorrenciaTurma.turma_id == turma.id)
        .order_by(OcorrenciaTurma.data_hora_inicio.desc())
        .first()
    )
    if ultima:
        proxima_data = ultima.data_hora_inicio.date() + timedelta(days=7)
    else:
        proxima_data = _proxima_data_para_dia_semana(hoje_utc, turma.dia_semana)

    geradas: list[OcorrenciaTurma] = []
    while proxima_data <= ate_data:
        inicio = datetime.combine(proxima_data, turma.hora_inicio)
        ocorrencia = OcorrenciaTurma(
            tenant_id=turma.tenant_id,
            turma_id=turma.id,
            data_hora_inicio=inicio,
            data_hora_fim=inicio + timedelta(minutes=turma.duracao_minutos),
            capacidade_vagas=turma.capacidade_vagas,
        )
        db.add(ocorrencia)
        geradas.append(ocorrencia)
        proxima_data += timedelta(days=7)

    if geradas:
        db.commit()
        for ocorrencia in geradas:
            db.refresh(ocorrencia)

    return geradas


def estender_janela_todas_turmas(db: Session) -> int:
    """Roda pra todas as turmas ativas de todas as empresas — chamada pelo
    cron diário (ver scripts/gerar_faturas_matricula.py)."""
    total = 0
    turmas = db.query(Turma).filter(Turma.ativa.is_(True)).all()
    for turma in turmas:
        total += len(gerar_ocorrencias(db, turma))
    return total
