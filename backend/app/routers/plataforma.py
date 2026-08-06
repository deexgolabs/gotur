from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import StatusAssinatura, UserRole
from app.models.onibus import Onibus
from app.models.usuario import Usuario
from app.schemas.plataforma import EmpresaPertoDoLimiteOut, MetricasPlataformaOut
from app.services.assinatura import atualizar_situacao_assinaturas

router = APIRouter(prefix="/plataforma", tags=["plataforma"])

LIMIAR_ALERTA = 0.8  # avisa quando a empresa já usou 80%+ do limite do plano


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
    mrr = sum(
        float(e.plano.preco_mensal)
        for e in empresas
        if e.plano and e.status_assinatura in (StatusAssinatura.ATIVA, StatusAssinatura.INADIMPLENTE)
    )

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
        mrr=round(mrr, 2),
        empresas_perto_do_limite=perto_do_limite,
    )
