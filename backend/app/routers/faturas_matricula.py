from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_staff
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import FormaPagamento, StatusFatura, StatusMatricula, UserRole
from app.models.academia import FaturaMatricula, Matricula
from app.models.usuario import Usuario
from app.schemas.matricula import FaturaMatriculaOut, PagarFaturaMatriculaRequest
from app.services.auditoria import registrar as registrar_auditoria
from app.services.pagamento_provider import DadosCartao, modo_simulado, obter_configuracao_plataforma, obter_provider

router = APIRouter(tags=["faturas-matricula"])


def _para_out(fatura: FaturaMatricula, *, pagamento_simulado: bool) -> FaturaMatriculaOut:
    return FaturaMatriculaOut(
        id=fatura.id,
        matricula_id=fatura.matricula_id,
        valor=float(fatura.valor),
        status=fatura.status,
        vencimento=fatura.vencimento,
        pago_em=fatura.pago_em,
        forma_pagamento=fatura.forma_pagamento,
        pix_copia_cola=fatura.pix_copia_cola,
        pix_expira_em=fatura.pix_expira_em,
        criado_em=fatura.criado_em,
        pagamento_simulado=pagamento_simulado,
    )


def _pode_mexer_na_fatura(usuario_atual: Usuario, fatura: FaturaMatricula) -> bool:
    eh_staff_da_empresa = usuario_atual.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN) and usuario_atual.tenant_id == fatura.tenant_id
    eh_dono = fatura.cliente_usuario_id == usuario_atual.id
    return eh_staff_da_empresa or eh_dono


@router.get("/faturas-matricula/minhas", response_model=list[FaturaMatriculaOut])
def minhas_faturas_matricula(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    faturas = (
        db.query(FaturaMatricula)
        .filter(FaturaMatricula.cliente_usuario_id == usuario_atual.id)
        .order_by(FaturaMatricula.vencimento.desc())
        .all()
    )
    resultado = []
    for fatura in faturas:
        empresa = db.get(Empresa, fatura.tenant_id)
        resultado.append(_para_out(fatura, pagamento_simulado=modo_simulado(empresa=empresa)))
    return resultado


@router.get("/matriculas/{matricula_id}/faturas", response_model=list[FaturaMatriculaOut])
def listar_faturas_da_matricula(
    matricula_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    matricula = db.get(Matricula, matricula_id)
    if not matricula or matricula.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matrícula não encontrada")

    empresa = db.get(Empresa, usuario_atual.tenant_id)
    simulado = modo_simulado(empresa=empresa)
    faturas = (
        db.query(FaturaMatricula)
        .filter(FaturaMatricula.matricula_id == matricula_id)
        .order_by(FaturaMatricula.vencimento.desc())
        .all()
    )
    return [_para_out(f, pagamento_simulado=simulado) for f in faturas]


def _marcar_fatura_paga(db: Session, fatura: FaturaMatricula, usuario_atual: Usuario | None, gateway_ref: str | None) -> None:
    fatura.status = StatusFatura.PAGA
    fatura.pago_em = datetime.utcnow()
    fatura.gateway_ref = gateway_ref
    fatura.pix_copia_cola = None
    fatura.pix_expira_em = None

    matricula = db.get(Matricula, fatura.matricula_id)
    if matricula:
        if matricula.status in (StatusMatricula.PENDENTE, StatusMatricula.INADIMPLENTE, StatusMatricula.SUSPENSA):
            matricula.status = StatusMatricula.ATIVA
        matricula.aulas_utilizadas_ciclo_atual = 0

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="pagamento_fatura_matricula",
        entidade_tipo="fatura_matricula",
        entidade_id=fatura.id,
        detalhes=f"Fatura #{fatura.id} paga, R$ {fatura.valor}",
        tenant_id=fatura.tenant_id,
    )


@router.post("/faturas-matricula/{fatura_id}/pagar", response_model=FaturaMatriculaOut)
def pagar_fatura_matricula(
    fatura_id: int,
    dados: PagarFaturaMatriculaRequest = PagarFaturaMatriculaRequest(),
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    """Pix, cartão, dinheiro ou outro — sem boleto (cobrança pequena e
    recorrente de consumidor final, o atrito de nome+CPF+endereço do
    boleto não compensa). Dinheiro/outro cobrem o aluno pagando na
    recepção, aprovados na hora igual em `reservas_aula.py`. Usa
    `obter_provider(empresa=...)`: é dinheiro do aluno pra academia, não
    confundir com `obter_provider(plataforma=...)` de faturas.py, que é a
    mensalidade da própria empresa na plataforma."""
    fatura = db.get(FaturaMatricula, fatura_id)
    if not fatura:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura não encontrada")
    if not _pode_mexer_na_fatura(usuario_atual, fatura):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")
    if fatura.status == StatusFatura.PAGA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Fatura já paga")
    if dados.forma_pagamento == FormaPagamento.BOLETO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Boleto não é aceito para mensalidade de academia")

    empresa = db.get(Empresa, fatura.tenant_id)
    simulado = modo_simulado(empresa=empresa)

    dados_cartao = None
    if dados.forma_pagamento == FormaPagamento.CARTAO and dados.mp_token:
        dados_cartao = DadosCartao(
            token=dados.mp_token,
            payment_method_id=dados.mp_payment_method_id or "",
            installments=dados.mp_installments or 1,
            payer_email=dados.mp_payer_email,
        )

    config_plataforma = obter_configuracao_plataforma(db)

    try:
        resultado_cobranca = obter_provider(
            empresa=empresa, taxa_transacao_percentual=config_plataforma.taxa_transacao_percentual
        ).cobrar(
            forma_pagamento=dados.forma_pagamento,
            valor=float(fatura.valor),
            referencia_pedido=f"fatura-matricula-{fatura.id}",
            dados_cartao=dados_cartao,
        )
    except ValueError as erro:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(erro))

    if resultado_cobranca.status == "recusado":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pagamento recusado pelo Mercado Pago. Tente outro cartão.")

    if resultado_cobranca.status == "pendente":
        fatura.forma_pagamento = dados.forma_pagamento
        fatura.pix_copia_cola = resultado_cobranca.pix_copia_cola
        fatura.pix_expira_em = resultado_cobranca.pix_expira_em
        fatura.gateway_ref = resultado_cobranca.gateway_ref
        db.commit()
        db.refresh(fatura)
        return _para_out(fatura, pagamento_simulado=simulado)

    fatura.forma_pagamento = dados.forma_pagamento
    _marcar_fatura_paga(db, fatura, usuario_atual, resultado_cobranca.gateway_ref)
    db.commit()
    db.refresh(fatura)
    return _para_out(fatura, pagamento_simulado=simulado)


@router.post("/faturas-matricula/{fatura_id}/confirmar-simulado", response_model=FaturaMatriculaOut)
def confirmar_fatura_matricula_simulado(
    fatura_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    fatura = db.get(FaturaMatricula, fatura_id)
    if not fatura:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura não encontrada")
    if not _pode_mexer_na_fatura(usuario_atual, fatura):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")

    empresa = db.get(Empresa, fatura.tenant_id)
    if not modo_simulado(empresa=empresa):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmação manual desabilitada: um gateway de pagamento real está configurado.",
        )
    if fatura.status == StatusFatura.PAGA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Fatura já paga")
    if not fatura.pix_copia_cola:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nenhum pagamento pendente para esta fatura")
    if fatura.pix_expira_em and fatura.pix_expira_em < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cobrança expirada, gere um novo pagamento")

    _marcar_fatura_paga(db, fatura, usuario_atual, f"SIMULADO-fatura-matricula-{fatura.id}")
    db.commit()
    db.refresh(fatura)
    return _para_out(fatura, pagamento_simulado=True)
