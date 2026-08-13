import secrets

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.cupom import Cupom
from app.models.empresa import Empresa
from app.models.enums import StatusPassagem, TipoCupom
from app.models.passagem import Passagem
from app.models.usuario import Usuario


def verificar_e_gerar_cupons_indicacao(db: Session, empresa: Empresa, cliente_usuario_id: int | None) -> tuple[Cupom, Cupom] | None:
    """Chamado depois de toda passagem confirmada — se o programa de
    indicação estiver ligado, esse cliente tiver sido indicado por outro
    (ver Usuario.indicado_por_usuario_id) e essa for a PRIMEIRA passagem
    confirmada dele nessa empresa, gera um cupom pra ele e outro pro
    indicador. Só dispara uma vez por indicado (na segunda compra em
    diante, `total` já é maior que 1). Não bloqueia nada se falhar; é
    só um bônus."""
    if not empresa.indicacao_ativa or not cliente_usuario_id:
        return None

    cliente = db.get(Usuario, cliente_usuario_id)
    if not cliente or not cliente.indicado_por_usuario_id:
        return None

    total = (
        db.query(func.count(Passagem.id))
        .filter(
            Passagem.tenant_id == empresa.id,
            Passagem.cliente_usuario_id == cliente_usuario_id,
            Passagem.status == StatusPassagem.CONFIRMADA,
        )
        .scalar()
    )
    if total != 1:
        return None

    desconto = empresa.indicacao_desconto_percentual or 10
    cupom_indicado = Cupom(
        tenant_id=empresa.id,
        codigo=f"INDICACAO{secrets.token_hex(3).upper()}",
        tipo=TipoCupom.PERCENTUAL,
        valor=desconto,
        max_usos=1,
        cliente_usuario_id=cliente_usuario_id,
    )
    cupom_indicador = Cupom(
        tenant_id=empresa.id,
        codigo=f"INDICACAO{secrets.token_hex(3).upper()}",
        tipo=TipoCupom.PERCENTUAL,
        valor=desconto,
        max_usos=1,
        cliente_usuario_id=cliente.indicado_por_usuario_id,
    )
    db.add_all([cupom_indicado, cupom_indicador])
    db.commit()
    db.refresh(cupom_indicado)
    db.refresh(cupom_indicador)
    return cupom_indicado, cupom_indicador
