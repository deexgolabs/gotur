from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import FormaPagamento, StatusAssinatura, StatusFatura, UserRole
from app.models.fatura_empresa import FaturaEmpresa
from app.models.usuario import Usuario
from app.schemas.fatura import FaturaOut
from app.services.assinatura import atualizar_situacao_assinaturas
from app.services.auditoria import registrar as registrar_auditoria
from app.services.pagamento_provider import obter_provider

router = APIRouter(tags=["faturas"])

DIAS_PARA_VENCIMENTO = 7


def _para_out(fatura: FaturaEmpresa) -> FaturaOut:
    return FaturaOut(
        id=fatura.id,
        empresa_id=fatura.empresa_id,
        empresa_nome=fatura.empresa.nome if fatura.empresa else None,
        plano_id=fatura.plano_id,
        plano_nome=fatura.plano.nome if fatura.plano else None,
        valor=float(fatura.valor),
        status=fatura.status,
        vencimento=fatura.vencimento,
        pago_em=fatura.pago_em,
        criado_em=fatura.criado_em,
    )


@router.post("/empresas/{empresa_id}/faturas", response_model=FaturaOut, status_code=status.HTTP_201_CREATED)
def gerar_fatura(
    empresa_id: int,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    empresa = db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa não encontrada")
    if not empresa.plano_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empresa sem plano definido")

    fatura = FaturaEmpresa(
        empresa_id=empresa.id,
        plano_id=empresa.plano_id,
        valor=empresa.plano.preco_mensal,
        status=StatusFatura.PENDENTE,
        vencimento=date.today() + timedelta(days=DIAS_PARA_VENCIMENTO),
    )
    db.add(fatura)
    db.commit()
    db.refresh(fatura)
    return _para_out(fatura)


@router.get("/empresas/{empresa_id}/faturas", response_model=list[FaturaOut])
def listar_faturas_da_empresa(
    empresa_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    eh_super_admin = usuario_atual.role == UserRole.SUPER_ADMIN
    eh_admin_da_propria_empresa = usuario_atual.role == UserRole.ADMIN_EMPRESA and usuario_atual.tenant_id == empresa_id
    if not eh_super_admin and not eh_admin_da_propria_empresa:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")

    atualizar_situacao_assinaturas(db)

    faturas = (
        db.query(FaturaEmpresa)
        .options(joinedload(FaturaEmpresa.empresa), joinedload(FaturaEmpresa.plano))
        .filter(FaturaEmpresa.empresa_id == empresa_id)
        .order_by(FaturaEmpresa.vencimento.desc())
        .all()
    )
    return [_para_out(f) for f in faturas]


@router.get("/faturas/minhas", response_model=list[FaturaOut])
def minhas_faturas(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    """Usa `get_current_user` (não `require_roles`) de propósito: mesmo com
    a empresa suspensa por falta de pagamento, o admin precisa conseguir
    ver e pagar a própria fatura para sair da suspensão."""
    if usuario_atual.role != UserRole.ADMIN_EMPRESA:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito ao admin da empresa")

    atualizar_situacao_assinaturas(db)
    faturas = (
        db.query(FaturaEmpresa)
        .options(joinedload(FaturaEmpresa.empresa), joinedload(FaturaEmpresa.plano))
        .filter(FaturaEmpresa.empresa_id == usuario_atual.tenant_id)
        .order_by(FaturaEmpresa.vencimento.desc())
        .all()
    )
    return [_para_out(f) for f in faturas]


@router.post("/faturas/{fatura_id}/pagar", response_model=FaturaOut)
def pagar_fatura(
    fatura_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    """Marca a fatura como paga. Super admin pode pagar qualquer fatura
    (ex: recebeu por fora); admin da empresa só a da própria empresa
    (autoatendimento — reaproveita o provedor de pagamento já usado para as
    passagens)."""
    fatura = db.get(FaturaEmpresa, fatura_id)
    if not fatura:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura não encontrada")

    eh_super_admin = usuario_atual.role == UserRole.SUPER_ADMIN
    eh_admin_da_propria_empresa = usuario_atual.role == UserRole.ADMIN_EMPRESA and usuario_atual.tenant_id == fatura.empresa_id
    if not eh_super_admin and not eh_admin_da_propria_empresa:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")
    if fatura.status == StatusFatura.PAGA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Fatura já paga")

    resultado_cobranca = obter_provider().cobrar(
        forma_pagamento=FormaPagamento.PIX,
        valor=float(fatura.valor),
        referencia_pedido=f"fatura-{fatura.id}",
    )

    fatura.status = StatusFatura.PAGA
    fatura.pago_em = datetime.now(timezone.utc)
    fatura.gateway_ref = resultado_cobranca.gateway_ref

    empresa = db.get(Empresa, fatura.empresa_id)
    if empresa and empresa.status_assinatura in (StatusAssinatura.INADIMPLENTE, StatusAssinatura.SUSPENSA, StatusAssinatura.TRIAL):
        empresa.status_assinatura = StatusAssinatura.ATIVA

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="pagamento_fatura",
        entidade_tipo="fatura_empresa",
        entidade_id=fatura.id,
        detalhes=f"Fatura #{fatura.id} paga, R$ {fatura.valor}",
        tenant_id=fatura.empresa_id,
    )

    db.commit()
    db.refresh(fatura)
    return _para_out(fatura)
