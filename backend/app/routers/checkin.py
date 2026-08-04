from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_staff
from app.database import get_db
from app.models.enums import StatusPassagem, UserRole
from app.models.onibus import Onibus
from app.models.passagem import Passagem
from app.models.poltrona_viagem import PoltronaViagem
from app.models.usuario import Usuario
from app.models.viagem import Viagem
from app.schemas.checkin import CheckinConsultaOut
from app.services.auditoria import registrar as registrar_auditoria
from app.services.pdf_service import DadosBilhete, gerar_bilhete_pdf
from app.services.qrcode_service import gerar_qrcode_png

router = APIRouter(tags=["checkin"])


def _buscar_passagem_por_localizador(db: Session, localizador: str) -> Passagem:
    passagem = (
        db.query(Passagem)
        .options(
            joinedload(Passagem.viagem).joinedload(Viagem.rota),
            joinedload(Passagem.viagem).joinedload(Viagem.onibus).joinedload(Onibus.empresa),
            joinedload(Passagem.poltrona_viagem).joinedload(PoltronaViagem.poltrona_onibus),
            joinedload(Passagem.parada_origem),
            joinedload(Passagem.parada_destino),
        )
        .filter(Passagem.localizador == localizador.upper())
        .first()
    )
    if not passagem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passagem não encontrada")
    return passagem


def _para_consulta(passagem: Passagem) -> CheckinConsultaOut:
    return CheckinConsultaOut(
        passagem_id=passagem.id,
        localizador=passagem.localizador,
        cliente_nome=passagem.cliente_nome,
        numero_poltrona=passagem.poltrona_viagem.poltrona_onibus.numero,
        origem=passagem.origem_trecho,
        destino=passagem.destino_trecho,
        data_hora_partida=passagem.viagem.data_hora_partida,
        status_passagem=passagem.status.value,
        checkin_em=passagem.checkin_em,
    )


@router.get("/passagens/{localizador}/qrcode")
def qrcode_da_passagem(
    localizador: str,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    passagem = _buscar_passagem_por_localizador(db, localizador)
    is_staff = usuario_atual.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN)
    if not is_staff and passagem.cliente_usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Você não tem acesso a esta passagem")

    png = gerar_qrcode_png(passagem.localizador)
    return Response(content=png, media_type="image/png")


@router.get("/passagens/{localizador}/bilhete.pdf")
def bilhete_em_pdf(
    localizador: str,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    passagem = _buscar_passagem_por_localizador(db, localizador)
    is_staff = usuario_atual.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN)
    if not is_staff and passagem.cliente_usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Você não tem acesso a esta passagem")

    pdf_bytes = gerar_bilhete_pdf(
        DadosBilhete(
            empresa_nome=passagem.viagem.onibus.empresa.nome if passagem.viagem.onibus.empresa else "",
            origem=passagem.origem_trecho,
            destino=passagem.destino_trecho,
            data_hora_partida=passagem.viagem.data_hora_partida,
            numero_poltrona=passagem.poltrona_viagem.poltrona_onibus.numero,
            categoria_poltrona=passagem.poltrona_viagem.poltrona_onibus.categoria,
            cliente_nome=passagem.cliente_nome,
            cliente_documento=passagem.cliente_documento,
            localizador=passagem.localizador,
            preco=float(passagem.preco),
        )
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="bilhete-{passagem.localizador}.pdf"'},
    )


@router.get("/checkin/{localizador}", response_model=CheckinConsultaOut)
def consultar_para_checkin(
    localizador: str,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    passagem = _buscar_passagem_por_localizador(db, localizador)
    if passagem.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passagem não encontrada")
    return _para_consulta(passagem)


@router.post("/checkin/{localizador}", response_model=CheckinConsultaOut)
def confirmar_checkin(
    localizador: str,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    passagem = _buscar_passagem_por_localizador(db, localizador)
    if passagem.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passagem não encontrada")
    if passagem.status != StatusPassagem.CONFIRMADA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Passagem não está confirmada")
    if passagem.checkin_em:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Check-in já realizado para esta passagem")

    passagem.checkin_em = datetime.now(timezone.utc)

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="checkin",
        entidade_tipo="passagem",
        entidade_id=passagem.id,
        detalhes=f"Localizador {passagem.localizador}, passageiro {passagem.cliente_nome}",
        tenant_id=passagem.tenant_id,
    )

    db.commit()
    db.refresh(passagem)
    return _para_consulta(passagem)
