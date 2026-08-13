from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.database import get_db
from app.models.checklist_viagem import ChecklistViagem
from app.models.enums import TipoViagemJornada, UserRole
from app.models.usuario import Usuario
from app.routers.jornadas import _motorista_atual, _validar_dono_do_trajeto
from app.schemas.checklist_viagem import ChecklistViagemCreate, ChecklistViagemOut

router = APIRouter(prefix="/checklists", tags=["checklists"])


@router.post("", response_model=ChecklistViagemOut, status_code=201)
def registrar_checklist(
    dados: ChecklistViagemCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA, UserRole.FUNCIONARIO, UserRole.MOTORISTA)),
):
    motorista_nome = dados.motorista_nome.strip()
    if usuario_atual.role == UserRole.MOTORISTA:
        motorista = _motorista_atual(db, usuario_atual)
        _validar_dono_do_trajeto(db, usuario_atual.tenant_id, dados.tipo_viagem, dados.referencia_id, motorista.id)
        motorista_nome = motorista.nome  # ignora o que veio do cliente — sempre o próprio nome

    checklist = ChecklistViagem(
        tenant_id=usuario_atual.tenant_id,
        motorista_nome=motorista_nome,
        tipo_viagem=dados.tipo_viagem,
        referencia_id=dados.referencia_id,
        pneus_ok=dados.pneus_ok,
        oleo_ok=dados.oleo_ok,
        combustivel_ok=dados.combustivel_ok,
        observacoes=dados.observacoes,
    )
    db.add(checklist)
    db.commit()
    db.refresh(checklist)
    return checklist


@router.get("", response_model=list[ChecklistViagemOut])
def listar_checklists(
    tipo_viagem: TipoViagemJornada | None = None,
    referencia_id: int | None = None,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA, UserRole.FUNCIONARIO, UserRole.MOTORISTA)),
):
    query = db.query(ChecklistViagem).filter(ChecklistViagem.tenant_id == usuario_atual.tenant_id)
    if usuario_atual.role == UserRole.MOTORISTA:
        query = query.filter(ChecklistViagem.motorista_nome == _motorista_atual(db, usuario_atual).nome)
    if tipo_viagem:
        query = query.filter(ChecklistViagem.tipo_viagem == tipo_viagem)
    if referencia_id is not None:
        query = query.filter(ChecklistViagem.referencia_id == referencia_id)
    return query.order_by(ChecklistViagem.criado_em.desc()).all()
