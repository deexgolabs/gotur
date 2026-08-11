from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import StatusAssinatura, StatusFatura, UserRole
from app.models.fatura_empresa import FaturaEmpresa
from app.models.onibus import Onibus
from app.models.passagem import Passagem
from app.models.usuario import Usuario
from app.schemas.plataforma import (
    CrescimentoEmpresaOut,
    EmpresaEmRiscoOut,
    EmpresaPertoDoLimiteOut,
    MetricasPlataformaOut,
    MrrMesOut,
)
from app.services.assinatura import atualizar_situacao_assinaturas

router = APIRouter(prefix="/plataforma", tags=["plataforma"])

LIMIAR_ALERTA = 0.8  # avisa quando a empresa já usou 80%+ do limite do plano
MESES_HISTORICO_MRR = 6


def _primeiro_dia_do_mes(referencia: date) -> date:
    return referencia.replace(day=1)


def _mes_anterior(referencia: date) -> date:
    primeiro = _primeiro_dia_do_mes(referencia)
    return (primeiro - timedelta(days=1)).replace(day=1)


def _ultimos_n_meses(n: int) -> list[date]:
    """Lista de "primeiro dia do mês" dos últimos `n` meses, do mais antigo
    pro mais recente (inclui o mês atual)."""
    meses = [_primeiro_dia_do_mes(date.today())]
    for _ in range(n - 1):
        meses.append(_mes_anterior(meses[-1]))
    return list(reversed(meses))


@router.get("/metricas", response_model=MetricasPlataformaOut)
def metricas_plataforma(
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    atualizar_situacao_assinaturas(db)

    empresas = db.query(Empresa).options(joinedload(Empresa.plano)).all()

    total = len(empresas)
    ativas = sum(1 for e in empresas if e.status_assinatura == StatusAssinatura.ATIVA)
    trial = sum(1 for e in empresas if e.status_assinatura == StatusAssinatura.TRIAL)
    inadimplentes = sum(1 for e in empresas if e.status_assinatura == StatusAssinatura.INADIMPLENTE)
    suspensas = sum(1 for e in empresas if e.status_assinatura == StatusAssinatura.SUSPENSA)
    desativadas = sum(1 for e in empresas if not e.ativo)
    mrr = sum(
        float(e.plano.preco_mensal)
        for e in empresas
        if e.plano and e.status_assinatura in (StatusAssinatura.ATIVA, StatusAssinatura.INADIMPLENTE)
    )

    # MRR histórico: soma do que foi efetivamente pago em cada um dos
    # últimos meses — diferente do MRR "corrente" acima (que é a
    # expectativa de hoje), isso mostra o que realmente entrou.
    inicio_historico = _ultimos_n_meses(MESES_HISTORICO_MRR)[0]
    faturas_pagas = (
        db.query(FaturaEmpresa)
        .filter(FaturaEmpresa.status == StatusFatura.PAGA, FaturaEmpresa.pago_em >= inicio_historico)
        .all()
    )
    mrr_por_mes: dict[str, float] = {}
    for fatura in faturas_pagas:
        chave = fatura.pago_em.strftime("%Y-%m")
        mrr_por_mes[chave] = mrr_por_mes.get(chave, 0.0) + float(fatura.valor)
    mrr_historico = [
        MrrMesOut(mes=mes.strftime("%Y-%m"), mrr=round(mrr_por_mes.get(mes.strftime("%Y-%m"), 0.0), 2))
        for mes in _ultimos_n_meses(MESES_HISTORICO_MRR)
    ]

    # Inadimplência agregada: quanto está vencido e não pago, somado.
    hoje = date.today()
    faturas_vencidas = (
        db.query(FaturaEmpresa)
        .filter(FaturaEmpresa.status == StatusFatura.PENDENTE, FaturaEmpresa.vencimento < hoje)
        .all()
    )
    inadimplencia_total = round(sum(float(f.valor) for f in faturas_vencidas), 2)

    # Carteira em risco: empresas inadimplentes ou já suspensas, com o
    # valor em atraso e há quanto tempo — pra priorizar quem contatar.
    valor_em_atraso_por_empresa: dict[int, float] = {}
    dias_em_atraso_por_empresa: dict[int, int] = {}
    for fatura in faturas_vencidas:
        valor_em_atraso_por_empresa[fatura.empresa_id] = valor_em_atraso_por_empresa.get(fatura.empresa_id, 0.0) + float(fatura.valor)
        dias = (hoje - fatura.vencimento).days
        dias_em_atraso_por_empresa[fatura.empresa_id] = max(dias_em_atraso_por_empresa.get(fatura.empresa_id, 0), dias)

    empresas_em_risco = [
        EmpresaEmRiscoOut(
            empresa_id=empresa.id,
            empresa_nome=empresa.nome,
            status_assinatura=empresa.status_assinatura.value,
            valor_em_atraso=round(valor_em_atraso_por_empresa.get(empresa.id, 0.0), 2),
            dias_em_atraso=dias_em_atraso_por_empresa.get(empresa.id, 0),
        )
        for empresa in empresas
        if empresa.status_assinatura in (StatusAssinatura.INADIMPLENTE, StatusAssinatura.SUSPENSA)
    ]
    empresas_em_risco.sort(key=lambda e: e.dias_em_atraso, reverse=True)

    # Quem cresce: compara passagens vendidas nos últimos 30 dias contra
    # os 30 dias anteriores, por empresa — sinaliza conta em expansão
    # (candidata a upgrade de plano) sem precisar olhar caso a caso.
    inicio_periodo_atual = hoje - timedelta(days=30)
    inicio_periodo_anterior = hoje - timedelta(days=60)

    contagem_atual = dict(
        db.query(Passagem.tenant_id, func.count(Passagem.id))
        .filter(Passagem.criado_em >= inicio_periodo_atual)
        .group_by(Passagem.tenant_id)
        .all()
    )
    contagem_anterior = dict(
        db.query(Passagem.tenant_id, func.count(Passagem.id))
        .filter(Passagem.criado_em >= inicio_periodo_anterior, Passagem.criado_em < inicio_periodo_atual)
        .group_by(Passagem.tenant_id)
        .all()
    )

    crescimento: list[CrescimentoEmpresaOut] = []
    for empresa in empresas:
        atual = contagem_atual.get(empresa.id, 0)
        anterior = contagem_anterior.get(empresa.id, 0)
        if atual == 0 and anterior == 0:
            continue
        variacao = round((atual - anterior) / anterior * 100, 1) if anterior else None
        crescimento.append(
            CrescimentoEmpresaOut(
                empresa_id=empresa.id,
                empresa_nome=empresa.nome,
                passagens_mes_atual=atual,
                passagens_mes_anterior=anterior,
                variacao_percentual=variacao,
            )
        )
    crescimento.sort(key=lambda c: (c.variacao_percentual is None, -(c.variacao_percentual or 0)))
    top_crescimento = crescimento[:5]

    perto_do_limite: list[EmpresaPertoDoLimiteOut] = []
    for empresa in empresas:
        if not empresa.plano or not empresa.ativo:
            continue

        if empresa.plano.max_onibus:
            total_onibus = (
                db.query(func.count(Onibus.id))
                .filter(Onibus.tenant_id == empresa.id, Onibus.ativo.is_(True))
                .scalar()
                or 0
            )
            if total_onibus >= empresa.plano.max_onibus * LIMIAR_ALERTA:
                perto_do_limite.append(
                    EmpresaPertoDoLimiteOut(
                        empresa_id=empresa.id,
                        empresa_nome=empresa.nome,
                        recurso="ônibus",
                        atual=total_onibus,
                        limite=empresa.plano.max_onibus,
                    )
                )

        if empresa.plano.max_funcionarios:
            total_funcionarios = (
                db.query(func.count(Usuario.id))
                .filter(
                    Usuario.tenant_id == empresa.id,
                    Usuario.role.in_((UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA)),
                    Usuario.ativo.is_(True),
                )
                .scalar()
                or 0
            )
            if total_funcionarios >= empresa.plano.max_funcionarios * LIMIAR_ALERTA:
                perto_do_limite.append(
                    EmpresaPertoDoLimiteOut(
                        empresa_id=empresa.id,
                        empresa_nome=empresa.nome,
                        recurso="funcionários",
                        atual=total_funcionarios,
                        limite=empresa.plano.max_funcionarios,
                    )
                )

    return MetricasPlataformaOut(
        total_empresas=total,
        empresas_ativas=ativas,
        empresas_trial=trial,
        empresas_inadimplentes=inadimplentes,
        empresas_suspensas=suspensas,
        empresas_desativadas=desativadas,
        mrr=round(mrr, 2),
        mrr_historico=mrr_historico,
        inadimplencia_total=inadimplencia_total,
        empresas_em_risco=empresas_em_risco,
        top_crescimento=top_crescimento,
        empresas_perto_do_limite=perto_do_limite,
    )
