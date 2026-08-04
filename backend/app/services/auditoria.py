from sqlalchemy.orm import Session

from app.models.auditoria import RegistroAuditoria
from app.models.usuario import Usuario


def registrar(
    db: Session,
    *,
    usuario: Usuario,
    acao: str,
    entidade_tipo: str,
    entidade_id: int | None = None,
    detalhes: str | None = None,
    tenant_id: int | None = None,
) -> None:
    """Adiciona um registro de auditoria à sessão (não commita — a rota
    chamadora deve commitar junto com a própria alteração, mantendo tudo
    atômico).

    `tenant_id` deve ser informado explicitamente quando a ação é de um
    cliente (que não tem tenant_id próprio) sobre algo de uma empresa —
    ex: comprar/cancelar uma passagem. Sem isso o registro cairia fora da
    consulta de auditoria da empresa.
    """
    db.add(
        RegistroAuditoria(
            tenant_id=tenant_id if tenant_id is not None else usuario.tenant_id,
            usuario_id=usuario.id,
            acao=acao,
            entidade_tipo=entidade_tipo,
            entidade_id=entidade_id,
            detalhes=detalhes,
        )
    )
