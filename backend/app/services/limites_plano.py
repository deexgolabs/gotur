"""Checagem dos limites do plano de assinatura da empresa (quantos ônibus,
funcionários e viagens/mês ela pode cadastrar). Sem plano atribuído, não há
limite (empresa em trial livre)."""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.empresa import Empresa
from app.models.enums import UserRole
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


def verificar_limite_viagens_mes(db: Session, empresa: Empresa) -> None:
    """Conta viagens com partida no mês corrente (não quando foram
    cadastradas) — é o número que corresponde à operação real da empresa."""
    if not empresa.plano:
        return
    agora = datetime.now(timezone.utc)
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if inicio_mes.month == 12:
        inicio_proximo_mes = inicio_mes.replace(year=inicio_mes.year + 1, month=1)
    else:
        inicio_proximo_mes = inicio_mes.replace(month=inicio_mes.month + 1)

    total = (
        db.query(func.count(Viagem.id))
        .filter(
            Viagem.tenant_id == empresa.id,
            Viagem.data_hora_partida >= inicio_mes.replace(tzinfo=None),
            Viagem.data_hora_partida < inicio_proximo_mes.replace(tzinfo=None),
        )
        .scalar()
        or 0
    )
    _bloquear_se_atingiu(empresa.plano.max_viagens_mes, total, "viagens neste mês")
