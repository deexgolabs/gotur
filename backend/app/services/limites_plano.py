"""Checagem dos limites do plano de assinatura da empresa (quantos ônibus,
funcionários e viagens/mês ela pode cadastrar — e os equivalentes pros
nichos não-viação: locais/sessões pra eventos, turmas/matrículas pra
academia). Sem plano atribuído, não há limite (empresa em trial livre)."""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.academia import Matricula, Turma
from app.models.empresa import Empresa
from app.models.enums import StatusMatricula, UserRole
from app.models.evento import Local, Sessao
from app.models.onibus import Onibus
from app.models.usuario import Usuario
from app.models.viagem import Viagem


def _bloquear_se_atingiu(limite: int | None, atual: int, recurso: str) -> None:
    if limite is not None and atual >= limite:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Limite do plano atingido: {limite} {recurso}. Faça upgrade do plano para continuar.",
        )


def verificar_limite_onibus(db: Session, empresa: Empresa) -> None:
    if not empresa.plano:
        return
    total = db.query(func.count(Onibus.id)).filter(Onibus.tenant_id == empresa.id, Onibus.ativo.is_(True)).scalar() or 0
    _bloquear_se_atingiu(empresa.plano.max_onibus, total, "ônibus ativos")


def verificar_limite_funcionarios(db: Session, empresa: Empresa) -> None:
    if not empresa.plano:
        return
    total = (
        db.query(func.count(Usuario.id))
        .filter(
            Usuario.tenant_id == empresa.id,
            Usuario.role.in_((UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA)),
            Usuario.ativo.is_(True),
        )
        .scalar()
        or 0
    )
    _bloquear_se_atingiu(empresa.plano.max_funcionarios, total, "funcionários ativos")


def _limites_do_mes_atual() -> tuple[datetime, datetime]:
    agora = datetime.now(timezone.utc)
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if inicio_mes.month == 12:
        inicio_proximo_mes = inicio_mes.replace(year=inicio_mes.year + 1, month=1)
    else:
        inicio_proximo_mes = inicio_mes.replace(month=inicio_mes.month + 1)
    return inicio_mes.replace(tzinfo=None), inicio_proximo_mes.replace(tzinfo=None)


def verificar_limite_viagens_mes(db: Session, empresa: Empresa) -> None:
    """Conta viagens com partida no mês corrente (não quando foram
    cadastradas) — é o número que corresponde à operação real da empresa."""
    if not empresa.plano:
        return
    inicio_mes, inicio_proximo_mes = _limites_do_mes_atual()
    total = (
        db.query(func.count(Viagem.id))
        .filter(
            Viagem.tenant_id == empresa.id,
            Viagem.data_hora_partida >= inicio_mes,
            Viagem.data_hora_partida < inicio_proximo_mes,
        )
        .scalar()
        or 0
    )
    _bloquear_se_atingiu(empresa.plano.max_viagens_mes, total, "viagens neste mês")


def verificar_limite_locais(db: Session, empresa: Empresa) -> None:
    if not empresa.plano:
        return
    total = db.query(func.count(Local.id)).filter(Local.tenant_id == empresa.id, Local.ativo.is_(True)).scalar() or 0
    _bloquear_se_atingiu(empresa.plano.max_locais, total, "locais ativos")


def verificar_limite_sessoes_mes(db: Session, empresa: Empresa) -> None:
    """Conta sessões com data/hora no mês corrente, mesmo espírito de
    verificar_limite_viagens_mes."""
    if not empresa.plano:
        return
    inicio_mes, inicio_proximo_mes = _limites_do_mes_atual()
    total = (
        db.query(func.count(Sessao.id))
        .filter(
            Sessao.tenant_id == empresa.id,
            Sessao.data_hora >= inicio_mes,
            Sessao.data_hora < inicio_proximo_mes,
        )
        .scalar()
        or 0
    )
    _bloquear_se_atingiu(empresa.plano.max_sessoes_mes, total, "sessões neste mês")


def verificar_limite_turmas(db: Session, empresa: Empresa) -> None:
    if not empresa.plano:
        return
    total = db.query(func.count(Turma.id)).filter(Turma.tenant_id == empresa.id, Turma.ativa.is_(True)).scalar() or 0
    _bloquear_se_atingiu(empresa.plano.max_turmas, total, "turmas ativas")


def verificar_limite_matriculas_ativas(db: Session, empresa: Empresa) -> None:
    """Conta matrículas que ainda ocupam uma vaga (tudo que não foi
    cancelado) — inclui pendente/inadimplente/suspensa, não só ativa,
    porque todas essas ainda contam como aluno vinculado à academia."""
    if not empresa.plano:
        return
    total = (
        db.query(func.count(Matricula.id))
        .filter(Matricula.tenant_id == empresa.id, Matricula.status != StatusMatricula.CANCELADA)
        .scalar()
        or 0
    )
    _bloquear_se_atingiu(empresa.plano.max_matriculas_ativas, total, "matrículas ativas")
