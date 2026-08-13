"""Cobrança recorrente automática — gera a fatura mensal de cada empresa
sozinho, sem o super admin precisar clicar em nada. Pensado pra rodar uma
vez por dia via tarefa agendada (ver scripts/gerar_faturas_mensais.py).

Regra do ciclo: a primeira fatura de uma empresa nasce `trial_dias_gratis`
dias depois do cadastro; a partir daí, cada fatura nova nasce 30 dias
depois do vencimento da anterior — não depende de quando ela foi paga, pra
não empurrar o ciclo pra frente indefinidamente se a empresa atrasar.
Empresa com fatura pendente em aberto não recebe uma nova (evita cobrança
duplicada)."""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models.empresa import Empresa
from app.models.enums import StatusAssinatura, StatusFatura, UserRole
from app.models.fatura_empresa import FaturaEmpresa
from app.models.usuario import Usuario
from app.services.notificacoes import enviar_fatura_gerada
from app.services.whatsapp_service import enviar_fatura_gerada_whatsapp

DIAS_PARA_VENCIMENTO = 7
CICLO_DIAS = 30


def _proxima_data_cobranca(empresa: Empresa, ultima_fatura: FaturaEmpresa | None) -> date:
    if ultima_fatura:
        return ultima_fatura.vencimento + timedelta(days=CICLO_DIAS)
    return empresa.criado_em.date() + timedelta(days=settings.trial_dias_gratis)


def _notificar(db: Session, empresa: Empresa, fatura: FaturaEmpresa, base_url: str) -> None:
    admin = (
        db.query(Usuario)
        .filter(Usuario.tenant_id == empresa.id, Usuario.role == UserRole.ADMIN_EMPRESA, Usuario.ativo.is_(True))
        .first()
    )
    link = f"{base_url.rstrip('/')}/pages/minhas-faturas.html"
    email = empresa.email_contato or (admin.email if admin else None)

    enviar_fatura_gerada(
        destinatario_email=email,
        empresa_nome=empresa.nome,
        valor=float(fatura.valor),
        vencimento=fatura.vencimento,
        link_pagamento=link,
    )
    enviar_fatura_gerada_whatsapp(
        telefone=admin.telefone if admin else None,
        empresa_nome=empresa.nome,
        valor=float(fatura.valor),
        vencimento=fatura.vencimento,
        link_pagamento=link,
    )


def gerar_faturas_do_dia(db: Session, base_url: str = "https://gotur.pythonanywhere.com") -> list[FaturaEmpresa]:
    """Roda pra todas as empresas que já venceram o próprio ciclo de
    cobrança hoje. Retorna as faturas criadas nesta execução."""
    hoje = date.today()
    geradas: list[FaturaEmpresa] = []

    empresas = (
        db.query(Empresa)
        .filter(
            Empresa.ativo.is_(True),
            Empresa.plano_id.isnot(None),
            Empresa.status_assinatura != StatusAssinatura.CANCELADA,
            Empresa.isento_cobranca.is_(False),
        )
        .all()
    )

    for empresa in empresas:
        tem_pendente = (
            db.query(FaturaEmpresa)
            .filter(FaturaEmpresa.empresa_id == empresa.id, FaturaEmpresa.status == StatusFatura.PENDENTE)
            .first()
        )
        if tem_pendente:
            continue

        ultima_fatura = (
            db.query(FaturaEmpresa)
            .filter(FaturaEmpresa.empresa_id == empresa.id)
            .order_by(FaturaEmpresa.vencimento.desc())
            .first()
        )
        if _proxima_data_cobranca(empresa, ultima_fatura) > hoje:
            continue

        fatura = FaturaEmpresa(
            empresa_id=empresa.id,
            plano_id=empresa.plano_id,
            valor=empresa.plano.preco_mensal,
            status=StatusFatura.PENDENTE,
            vencimento=hoje + timedelta(days=DIAS_PARA_VENCIMENTO),
        )
        db.add(fatura)
        db.commit()
        db.refresh(fatura)
        geradas.append(fatura)

        _notificar(db, empresa, fatura, base_url)

    return geradas
