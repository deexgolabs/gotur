from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_staff
from app.database import get_db
from app.models.academia import OcorrenciaTurma, ReservaAula
from app.models.enums import StatusPassagem, UserRole
from app.models.usuario import Usuario
from app.schemas.checkin import CheckinAcademiaConsultaOut
from app.services.auditoria import registrar as registrar_auditoria
from app.services.qrcode_service import gerar_qrcode_png

router = APIRouter(tags=["checkin-academia"])


def _buscar_reserva_por_codigo(db: Session, codigo: str) -> ReservaAula:
    reserva = (
        db.query(ReservaAula)
        .options(joinedload(ReservaAula.ocorrencia_turma).joinedload(OcorrenciaTurma.turma))
        .filter(ReservaAula.codigo == codigo.upper())
        .first()
    )
    if not reserva:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva não encontrada")
    return reserva


def _para_consulta(db: Session, reserva: ReservaAula) -> CheckinAcademiaConsultaOut:
    ocorrencia = reserva.ocorrencia_turma
    cliente_nome = reserva.cliente_nome
    if not cliente_nome and reserva.cliente_usuario_id:
        cliente = db.get(Usuario, reserva.cliente_usuario_id)
        cliente_nome = cliente.nome if cliente else None
    return CheckinAcademiaConsultaOut(
        reserva_id=reserva.id,
        codigo=reserva.codigo,
        cliente_nome=cliente_nome or "",
        nome_turma=ocorrencia.turma.nome if ocorrencia and ocorrencia.turma else "",
        data_hora_inicio=ocorrencia.data_hora_inicio if ocorrencia else None,
        status_reserva=reserva.status.value,
        checkin_em=reserva.checkin_em,
    )


@router.get("/reservas/{codigo}/qrcode")
def qrcode_da_reserva(
    codigo: str,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    reserva = _buscar_reserva_por_codigo(db, codigo)
    is_staff = usuario_atual.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN)
    if not is_staff and reserva.cliente_usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Você não tem acesso a esta reserva")

    png = gerar_qrcode_png(reserva.codigo)
    return Response(content=png, media_type="image/png")


@router.get("/checkin-academia/{codigo}", response_model=CheckinAcademiaConsultaOut)
def consultar_para_checkin(
    codigo: str,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    reserva = _buscar_reserva_por_codigo(db, codigo)
    if reserva.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva não encontrada")
    return _para_consulta(db, reserva)


@router.post("/checkin-academia/{codigo}", response_model=CheckinAcademiaConsultaOut)
def confirmar_checkin(
    codigo: str,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    reserva = _buscar_reserva_por_codigo(db, codigo)
    if reserva.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva não encontrada")
    if reserva.status != StatusPassagem.CONFIRMADA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reserva não está confirmada")
    if reserva.checkin_em:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Check-in já realizado para esta reserva")

    reserva.checkin_em = datetime.utcnow()

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="checkin_academia",
        entidade_tipo="reserva_aula",
        entidade_id=reserva.id,
        detalhes=f"Código {reserva.codigo}, aluno {reserva.cliente_nome}",
        tenant_id=reserva.tenant_id,
    )

    db.commit()
    db.refresh(reserva)
    return _para_consulta(db, reserva)
