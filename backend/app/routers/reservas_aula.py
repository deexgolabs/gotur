from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_staff
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import FormaPagamento, StatusMatricula, StatusPassagem, TipoMatricula, TipoReserva, UserRole
from app.models.academia import Matricula, OcorrenciaTurma, ReservaAula
from app.models.usuario import Usuario
from app.schemas.reserva_aula import CriarReservaRequest, ReservaAulaOut
from app.services.codigo import gerar_localizador
from app.services.pagamento_provider import DadosCartao, obter_configuracao_plataforma, obter_provider

router = APIRouter(tags=["reservas-aula"])

FORMAS_PAGAMENTO_AVULSA_PERMITIDAS = (FormaPagamento.CARTAO, FormaPagamento.DINHEIRO, FormaPagamento.OUTRO)


def _gerar_codigo_unico_reserva(db: Session) -> str:
    codigo = gerar_localizador()
    while db.query(ReservaAula).filter(ReservaAula.codigo == codigo).first():
        codigo = gerar_localizador()
    return codigo


def _para_out(reserva: ReservaAula) -> ReservaAulaOut:
    ocorrencia = reserva.ocorrencia_turma
    return ReservaAulaOut(
        id=reserva.id,
        ocorrencia_turma_id=reserva.ocorrencia_turma_id,
        nome_turma=ocorrencia.turma.nome if ocorrencia and ocorrencia.turma else None,
        data_hora_inicio=ocorrencia.data_hora_inicio if ocorrencia else None,
        cliente_nome=reserva.cliente_nome,
        cliente_documento=reserva.cliente_documento,
        tipo_reserva=reserva.tipo_reserva,
        status=reserva.status,
        preco_pago=float(reserva.preco_pago) if reserva.preco_pago is not None else None,
        forma_pagamento=reserva.forma_pagamento,
        codigo=reserva.codigo,
        criado_em=reserva.criado_em,
        checkin_em=reserva.checkin_em,
        cancelada_em=reserva.cancelada_em,
    )


def _vagas_ocupadas(db: Session, ocorrencia_id: int) -> int:
    return (
        db.query(ReservaAula)
        .filter(ReservaAula.ocorrencia_turma_id == ocorrencia_id, ReservaAula.status == StatusPassagem.CONFIRMADA)
        .count()
    )


@router.post("/ocorrencias-turma/{ocorrencia_id}/reservas", response_model=ReservaAulaOut, status_code=status.HTTP_201_CREATED)
def reservar_vaga(
    ocorrencia_id: int,
    dados: CriarReservaRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    ocorrencia = (
        db.query(OcorrenciaTurma)
        .options(joinedload(OcorrenciaTurma.turma))
        .filter(OcorrenciaTurma.id == ocorrencia_id)
        .first()
    )
    if not ocorrencia:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ocorrência não encontrada")
    if ocorrencia.cancelada:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta aula foi cancelada")
    if ocorrencia.data_hora_inicio < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta aula já aconteceu")

    if _vagas_ocupadas(db, ocorrencia.id) >= ocorrencia.capacidade_vagas:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sem vagas disponíveis para esta aula")

    is_staff = usuario_atual.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN)

    if dados.matricula_id is not None:
        matricula = db.get(Matricula, dados.matricula_id)
        if not matricula or matricula.tenant_id != ocorrencia.tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matrícula não encontrada")
        if not is_staff and matricula.cliente_usuario_id != usuario_atual.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Esta matrícula não pertence a você")
        if matricula.status == StatusMatricula.SUSPENSA:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Matrícula suspensa por inadimplência. Regularize o pagamento pra continuar reservando aulas.",
            )
        if matricula.status not in (StatusMatricula.ATIVA, StatusMatricula.INADIMPLENTE):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Matrícula não está ativa")
        if matricula.tipo == TipoMatricula.PACOTE_AULAS and matricula.aulas_utilizadas_ciclo_atual >= (matricula.aulas_por_ciclo or 0):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pacote de aulas esgotado neste ciclo")

        reserva = ReservaAula(
            tenant_id=ocorrencia.tenant_id,
            ocorrencia_turma_id=ocorrencia.id,
            cliente_usuario_id=matricula.cliente_usuario_id,
            matricula_id=matricula.id,
            tipo_reserva=TipoReserva.MATRICULA,
            status=StatusPassagem.CONFIRMADA,
            codigo=_gerar_codigo_unico_reserva(db),
        )
        db.add(reserva)
        if matricula.tipo == TipoMatricula.PACOTE_AULAS:
            matricula.aulas_utilizadas_ciclo_atual += 1
        db.commit()
        db.refresh(reserva)
        return _para_out(reserva)

    # Caminho avulso (drop-in) — exige preço avulso configurado na turma.
    turma = ocorrencia.turma
    if not turma.preco_avulso:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Esta turma não aceita aula avulsa sem matrícula")
    if dados.forma_pagamento not in FORMAS_PAGAMENTO_AVULSA_PERMITIDAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aula avulsa só aceita cartão, dinheiro ou outro (Pix não está disponível para esta modalidade)",
        )

    cliente_usuario_id = usuario_atual.id if usuario_atual.role == UserRole.CLIENTE else None
    if not cliente_usuario_id and not (dados.cliente_nome and dados.cliente_documento):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe nome e documento do cliente")

    empresa = db.get(Empresa, ocorrencia.tenant_id)
    preco_final = float(turma.preco_avulso)

    dados_cartao = None
    if dados.forma_pagamento == FormaPagamento.CARTAO and dados.mp_token:
        dados_cartao = DadosCartao(
            token=dados.mp_token,
            payment_method_id=dados.mp_payment_method_id or "",
            installments=dados.mp_installments or 1,
            payer_email=dados.mp_payer_email,
            payer_documento=dados.cliente_documento,
        )

    config_plataforma = obter_configuracao_plataforma(db)

    try:
        resultado_cobranca = obter_provider(
            empresa, taxa_transacao_percentual=config_plataforma.taxa_transacao_percentual
        ).cobrar(
            forma_pagamento=dados.forma_pagamento,
            valor=preco_final,
            referencia_pedido=f"ocorrencia-{ocorrencia.id}-usuario-{usuario_atual.id}",
            dados_cartao=dados_cartao,
        )
    except ValueError as erro:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(erro))

    if resultado_cobranca.status == "recusado":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pagamento recusado pelo Mercado Pago. Tente outro cartão.")
    if resultado_cobranca.status == "pendente":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não foi possível confirmar o pagamento na hora para esta forma de pagamento. Tente novamente.",
        )

    reserva = ReservaAula(
        tenant_id=ocorrencia.tenant_id,
        ocorrencia_turma_id=ocorrencia.id,
        cliente_usuario_id=cliente_usuario_id,
        cliente_nome=dados.cliente_nome or usuario_atual.nome,
        cliente_documento=dados.cliente_documento,
        tipo_reserva=TipoReserva.AVULSA,
        status=StatusPassagem.CONFIRMADA,
        preco_pago=preco_final,
        forma_pagamento=dados.forma_pagamento,
        gateway_ref=resultado_cobranca.gateway_ref,
        codigo=_gerar_codigo_unico_reserva(db),
    )
    db.add(reserva)
    db.commit()
    db.refresh(reserva)
    return _para_out(reserva)


def _buscar_reserva(db: Session, reserva_id: int, usuario_atual: Usuario) -> ReservaAula:
    reserva = (
        db.query(ReservaAula)
        .options(joinedload(ReservaAula.ocorrencia_turma).joinedload(OcorrenciaTurma.turma))
        .filter(ReservaAula.id == reserva_id)
        .first()
    )
    if not reserva:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva não encontrada")
    is_staff = usuario_atual.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN) and usuario_atual.tenant_id == reserva.tenant_id
    eh_dono = reserva.cliente_usuario_id == usuario_atual.id
    if not is_staff and not eh_dono:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")
    return reserva


@router.post("/reservas/{reserva_id}/cancelar", response_model=ReservaAulaOut)
def cancelar_reserva(
    reserva_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    reserva = _buscar_reserva(db, reserva_id, usuario_atual)
    if reserva.status == StatusPassagem.CANCELADA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reserva já cancelada")

    reserva.status = StatusPassagem.CANCELADA
    reserva.cancelada_em = datetime.utcnow()

    if reserva.matricula_id:
        matricula = db.get(Matricula, reserva.matricula_id)
        if matricula and matricula.tipo == TipoMatricula.PACOTE_AULAS and matricula.aulas_utilizadas_ciclo_atual > 0:
            matricula.aulas_utilizadas_ciclo_atual -= 1

    db.commit()
    db.refresh(reserva)
    return _para_out(reserva)


@router.get("/ocorrencias-turma/{ocorrencia_id}/reservas", response_model=list[ReservaAulaOut])
def listar_reservas_da_ocorrencia(
    ocorrencia_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    ocorrencia = db.get(OcorrenciaTurma, ocorrencia_id)
    if not ocorrencia or ocorrencia.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ocorrência não encontrada")

    reservas = (
        db.query(ReservaAula)
        .options(joinedload(ReservaAula.ocorrencia_turma).joinedload(OcorrenciaTurma.turma))
        .filter(ReservaAula.ocorrencia_turma_id == ocorrencia_id)
        .order_by(ReservaAula.criado_em)
        .all()
    )
    return [_para_out(r) for r in reservas]


@router.get("/reservas/minhas", response_model=list[ReservaAulaOut])
def minhas_reservas(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    reservas = (
        db.query(ReservaAula)
        .options(joinedload(ReservaAula.ocorrencia_turma).joinedload(OcorrenciaTurma.turma))
        .filter(ReservaAula.cliente_usuario_id == usuario_atual.id)
        .order_by(ReservaAula.criado_em.desc())
        .all()
    )
    return [_para_out(r) for r in reservas]
