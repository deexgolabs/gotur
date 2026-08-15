from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_staff
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import StatusPassagem, UserRole
from app.models.evento import AssentoSessao, Ingresso, Local, Sessao
from app.models.usuario import Usuario
from app.schemas.checkin import CheckinEventoConsultaOut
from app.services.auditoria import registrar as registrar_auditoria
from app.services.pdf_service import DadosIngresso, gerar_ingresso_pdf
from app.services.qrcode_service import gerar_qrcode_png

router = APIRouter(tags=["checkin-eventos"])


def _buscar_ingresso_por_codigo(db: Session, codigo: str) -> Ingresso:
    ingresso = (
        db.query(Ingresso)
        .options(
            joinedload(Ingresso.sessao).joinedload(Sessao.local).joinedload(Local.empresa) if False else joinedload(Ingresso.sessao).joinedload(Sessao.local),
            joinedload(Ingresso.assento_sessao).joinedload(AssentoSessao.assento_local),
        )
        .filter(Ingresso.codigo == codigo.upper())
        .first()
    )
    if not ingresso:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingresso não encontrado")
    return ingresso


def _para_consulta(ingresso: Ingresso) -> CheckinEventoConsultaOut:
    return CheckinEventoConsultaOut(
        ingresso_id=ingresso.id,
        codigo=ingresso.codigo,
        cliente_nome=ingresso.cliente_nome,
        numero_assento=ingresso.assento_sessao.assento_local.numero,
        nome_evento=ingresso.sessao.nome_evento,
        local_nome=ingresso.sessao.local.nome,
        data_hora=ingresso.sessao.data_hora,
        status_ingresso=ingresso.status.value,
        checkin_em=ingresso.checkin_em,
    )


@router.get("/ingressos/{codigo}/qrcode")
def qrcode_do_ingresso(
    codigo: str,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    ingresso = _buscar_ingresso_por_codigo(db, codigo)
    is_staff = usuario_atual.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN)
    if not is_staff and ingresso.cliente_usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Você não tem acesso a este ingresso")

    png = gerar_qrcode_png(ingresso.codigo)
    return Response(content=png, media_type="image/png")


@router.get("/ingressos/{codigo}/bilhete.pdf")
def bilhete_ingresso_em_pdf(
    codigo: str,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    ingresso = _buscar_ingresso_por_codigo(db, codigo)
    is_staff = usuario_atual.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN)
    if not is_staff and ingresso.cliente_usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Você não tem acesso a este ingresso")

    empresa = db.get(Empresa, ingresso.tenant_id)
    pdf_bytes = gerar_ingresso_pdf(
        DadosIngresso(
            empresa_nome=empresa.nome if empresa else "",
            nome_evento=ingresso.sessao.nome_evento,
            local_nome=ingresso.sessao.local.nome,
            data_hora=ingresso.sessao.data_hora,
            numero_assento=ingresso.assento_sessao.assento_local.numero,
            categoria_assento=ingresso.assento_sessao.assento_local.categoria,
            cliente_nome=ingresso.cliente_nome,
            cliente_documento=ingresso.cliente_documento,
            codigo=ingresso.codigo,
            preco=float(ingresso.preco),
        )
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="ingresso-{ingresso.codigo}.pdf"'},
    )


@router.get("/checkin-eventos/{codigo}", response_model=CheckinEventoConsultaOut)
def consultar_para_checkin(
    codigo: str,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    ingresso = _buscar_ingresso_por_codigo(db, codigo)
    if ingresso.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingresso não encontrado")
    return _para_consulta(ingresso)


@router.post("/checkin-eventos/{codigo}", response_model=CheckinEventoConsultaOut)
def confirmar_checkin(
    codigo: str,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    ingresso = _buscar_ingresso_por_codigo(db, codigo)
    if ingresso.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingresso não encontrado")
    if ingresso.status != StatusPassagem.CONFIRMADA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ingresso não está confirmado")
    if ingresso.checkin_em:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Check-in já realizado para este ingresso")

    ingresso.checkin_em = datetime.now(timezone.utc)

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="checkin_evento",
        entidade_tipo="ingresso",
        entidade_id=ingresso.id,
        detalhes=f"Código {ingresso.codigo}, passageiro {ingresso.cliente_nome}",
        tenant_id=ingresso.tenant_id,
    )

    db.commit()
    db.refresh(ingresso)
    return _para_consulta(ingresso)
