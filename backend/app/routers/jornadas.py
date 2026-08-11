from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.database import get_db
from app.models.enums import TipoViagemJornada, UserRole
from app.models.jornada_motorista import JornadaMotorista
from app.models.usuario import Usuario
from app.schemas.jornada_motorista import IniciarJornadaRequest, JornadaMotoristaOut, ResumoJornadaOut

router = APIRouter(prefix="/jornadas", tags=["jornadas"])

# Jornada diária normal de referência (CLT / Lei do Motorista 13.103/2015)
# — só usada pra avisar a empresa, nunca bloqueia o registro.
LIMITE_HORAS_JORNADA = 8.0


def _agora() -> datetime:
    # SQLite devolve datetime "naive" depois de um refresh (perde o
    # tzinfo), então pra poder subtrair com o que vem do banco sem
    # TypeError, geramos "agora" já naive (mas em UTC) desde o início.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _horas(inicio: datetime, fim: datetime | None) -> float:
    fim_efetivo = fim or _agora()
    return round((fim_efetivo - inicio).total_seconds() / 3600, 2)


def _para_out(jornada: JornadaMotorista) -> JornadaMotoristaOut:
    return JornadaMotoristaOut(
        id=jornada.id,
        motorista_nome=jornada.motorista_nome,
        tipo_viagem=jornada.tipo_viagem,
        referencia_id=jornada.referencia_id,
        inicio=jornada.inicio,
        fim=jornada.fim,
        horas=_horas(jornada.inicio, jornada.fim),
        criado_em=jornada.criado_em,
    )


def _horas_ultimas_24h(db: Session, tenant_id: int, motorista_nome: str, referencia: datetime) -> float:
    janela_inicio = referencia - timedelta(hours=24)
    jornadas = (
        db.query(JornadaMotorista)
        .filter(
            JornadaMotorista.tenant_id == tenant_id,
            JornadaMotorista.motorista_nome == motorista_nome,
            JornadaMotorista.inicio < referencia,
            or_(JornadaMotorista.fim.is_(None), JornadaMotorista.fim > janela_inicio),
        )
        .all()
    )
    total = 0.0
    for j in jornadas:
        inicio_considerado = max(j.inicio, janela_inicio)
        fim_considerado = min(j.fim or referencia, referencia)
        if fim_considerado > inicio_considerado:
            total += (fim_considerado - inicio_considerado).total_seconds() / 3600
    return round(total, 2)


@router.post("", response_model=JornadaMotoristaOut, status_code=status.HTTP_201_CREATED)
def iniciar_jornada(
    dados: IniciarJornadaRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA, UserRole.FUNCIONARIO)),
):
    jornada = JornadaMotorista(
        tenant_id=usuario_atual.tenant_id,
        motorista_nome=dados.motorista_nome.strip(),
        tipo_viagem=dados.tipo_viagem,
        referencia_id=dados.referencia_id,
        inicio=_agora(),
    )
    db.add(jornada)
    db.commit()
    db.refresh(jornada)
    return _para_out(jornada)


@router.patch("/{jornada_id}/encerrar", response_model=JornadaMotoristaOut)
def encerrar_jornada(
    jornada_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA, UserRole.FUNCIONARIO)),
):
    jornada = db.get(JornadaMotorista, jornada_id)
    if not jornada or jornada.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jornada não encontrada")
    if jornada.fim is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Essa jornada já foi encerrada.")
    jornada.fim = _agora()
    db.commit()
    db.refresh(jornada)
    return _para_out(jornada)


@router.get("/resumo", response_model=ResumoJornadaOut)
def resumo_jornada(
    motorista_nome: str,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA, UserRole.FUNCIONARIO)),
):
    """Soma quantas horas esse motorista já trabalhou nas últimas 24h
    (jornadas fechadas + a que estiver em andamento, se houver) e avisa se
    passou do limite de referência da Lei do Motorista."""
    horas = _horas_ultimas_24h(db, usuario_atual.tenant_id, motorista_nome.strip(), _agora())
    return ResumoJornadaOut(horas_ultimas_24h=horas, acima_do_limite=horas > LIMITE_HORAS_JORNADA)


@router.get("", response_model=list[JornadaMotoristaOut])
def listar_jornadas(
    motorista_nome: str | None = None,
    tipo_viagem: TipoViagemJornada | None = None,
    referencia_id: int | None = None,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA, UserRole.FUNCIONARIO)),
):
    query = db.query(JornadaMotorista).filter(JornadaMotorista.tenant_id == usuario_atual.tenant_id)
    if motorista_nome:
        query = query.filter(JornadaMotorista.motorista_nome == motorista_nome.strip())
    if tipo_viagem:
        query = query.filter(JornadaMotorista.tipo_viagem == tipo_viagem)
    if referencia_id is not None:
        query = query.filter(JornadaMotorista.referencia_id == referencia_id)
    jornadas = query.order_by(JornadaMotorista.inicio.desc()).all()
    return [_para_out(j) for j in jornadas]
