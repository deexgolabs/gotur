import secrets

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.cupom import Cupom
from app.models.empresa import Empresa
from app.models.enums import StatusPassagem, TipoCupom
from app.models.passagem import Passagem


def verificar_e_gerar_cupom_fidelidade(db: Session, empresa: Empresa, cliente_usuario_id: int | None) -> Cupom | None:
    """Chamado depois de toda passagem confirmada — se o programa de
    fidelidade estiver ligado e esse cliente (com conta, não venda avulsa
    de balcão) tiver acabado de completar mais um "ciclo" de N passagens,
    gera automaticamente um cupom pessoal de desconto pra ele. Não
    bloqueia nada se falhar em gerar; é só um bônus."""
    if not empresa.fidelidade_ativa or not cliente_usuario_id:
        return None
    necessarias = empresa.fidelidade_passagens_necessarias or 0
    if necessarias <= 0:
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
    if not total or total % necessarias != 0:
        return None

    codigo = f"FIDELIDADE{secrets.token_hex(3).upper()}"
    cupom = Cupom(
        tenant_id=empresa.id,
        codigo=codigo,
        tipo=TipoCupom.PERCENTUAL,
        valor=empresa.fidelidade_desconto_percentual or 10,
        max_usos=1,
        cliente_usuario_id=cliente_usuario_id,
    )
    db.add(cupom)
    db.commit()
    db.refresh(cupom)
    return cupom
