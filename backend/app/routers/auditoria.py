from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles
from app.database import get_db
from app.models.auditoria import RegistroAuditoria
from app.models.enums import UserRole
from app.models.usuario import Usuario
from app.schemas.auditoria import RegistroAuditoriaOut

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.get("", response_model=list[RegistroAuditoriaOut])
def listar_auditoria(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
    limite: int = 200,
):
    registros = (
        db.query(RegistroAuditoria)
        .options(joinedload(RegistroAuditoria.usuario))
        .filter(RegistroAuditoria.tenant_id == usuario_atual.tenant_id)
        .order_by(RegistroAuditoria.criado_em.desc())
        .limit(min(limite, 1000))
        .all()
    )
    return [
        RegistroAuditoriaOut(
            id=r.id,
            usuario_id=r.usuario_id,
            usuario_nome=r.usuario.nome if r.usuario else None,
            acao=r.acao,
            entidade_tipo=r.entidade_tipo,
            entidade_id=r.entidade_id,
            detalhes=r.detalhes,
            criado_em=r.criado_em,
        )
        for r in registros
    ]
