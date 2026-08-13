from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models.configuracao_plataforma import ConfiguracaoPlataforma
from app.models.empresa import Empresa
from app.models.enums import FormaPagamento, StatusAssinatura, StatusFatura, UserRole
from app.models.fatura_empresa import FaturaEmpresa
from app.models.usuario import Usuario
from app.schemas.fatura import FaturaOut
from app.services.assinatura import atualizar_situacao_assinaturas
from app.services.auditoria import registrar as registrar_auditoria
from app.services.pagamento_provider import modo_simulado, obter_configuracao_plataforma, obter_provider

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
        pix_copia_cola=fatura.pix_copia_cola,
        pix_expira_em=fatura.pix_expira_em,
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


def _pode_mexer_na_fatura(usuario_atual: Usuario, fatura: FaturaEmpresa) -> bool:
    eh_super_admin = usuario_atual.role == UserRole.SUPER_ADMIN
    eh_admin_da_propria_empresa = usuario_atual.role == UserRole.ADMIN_EMPRESA and usuario_atual.tenant_id == fatura.empresa_id
    return eh_super_admin or eh_admin_da_propria_empresa


def _marcar_fatura_paga(db: Session, fatura: FaturaEmpresa, usuario_atual: Usuario | None, gateway_ref: str | None) -> None:
    fatura.status = StatusFatura.PAGA
    fatura.pago_em = datetime.now(timezone.utc)
    fatura.gateway_ref = gateway_ref
    fatura.pix_copia_cola = None
    fatura.pix_expira_em = None

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


@router.post("/faturas/{fatura_id}/pagar", response_model=FaturaOut)
def pagar_fatura(
    fatura_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    """Inicia o pagamento da fatura via Pix. Super admin pode pagar
    qualquer fatura (ex: recebeu por fora); admin da empresa só a da
    própria empresa (autoatendimento — reaproveita o provedor de pagamento
    já usado para as passagens). Em modo simulado, gera um código Pix
    pendente que precisa ser confirmado em `/faturas/{id}/confirmar-simulado`
    (com um gateway real, quem confirma é o próprio webhook do gateway)."""
    fatura = db.get(FaturaEmpresa, fatura_id)
    if not fatura:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura não encontrada")
    if not _pode_mexer_na_fatura(usuario_atual, fatura):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")
    if fatura.status == StatusFatura.PAGA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Fatura já paga")

    plataforma = obter_configuracao_plataforma(db)
    resultado_cobranca = obter_provider(plataforma=plataforma).cobrar(
        forma_pagamento=FormaPagamento.PIX,
        valor=float(fatura.valor),
        referencia_pedido=f"fatura-{fatura.id}",
    )

    if resultado_cobranca.status == "pendente":
        fatura.pix_copia_cola = resultado_cobranca.pix_copia_cola
        fatura.pix_expira_em = resultado_cobranca.pix_expira_em
        fatura.gateway_ref = resultado_cobranca.gateway_ref
        db.commit()
        db.refresh(fatura)
        return _para_out(fatura)

    _marcar_fatura_paga(db, fatura, usuario_atual, resultado_cobranca.gateway_ref)
    db.commit()
    db.refresh(fatura)
    return _para_out(fatura)


@router.post("/faturas/{fatura_id}/confirmar-simulado", response_model=FaturaOut)
def confirmar_pagamento_fatura_simulado(
    fatura_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    """Simula o webhook que um gateway real chamaria quando o Pix da
    fatura cai na conta. Só existe em modo simulado."""
    if not modo_simulado(plataforma=obter_configuracao_plataforma(db)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmação manual desabilitada: um gateway de pagamento real está configurado.",
        )

    fatura = db.get(FaturaEmpresa, fatura_id)
    if not fatura:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura não encontrada")
    if not _pode_mexer_na_fatura(usuario_atual, fatura):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")
    if fatura.status == StatusFatura.PAGA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Fatura já paga")
    if not fatura.pix_copia_cola:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nenhum Pix pendente para esta fatura")
    if fatura.pix_expira_em and fatura.pix_expira_em < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pix expirado, gere um novo pagamento")

    _marcar_fatura_paga(db, fatura, usuario_atual, f"SIMULADO-fatura-{fatura.id}")
    db.commit()
    db.refresh(fatura)
    return _para_out(fatura)
