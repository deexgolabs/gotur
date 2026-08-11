from datetime import datetime

from sqlalchemy.orm import Session

from app.models.cupom import Cupom
from app.models.enums import TipoCupom


class CupomInvalido(Exception):
    pass


def buscar_cupom_valido(db: Session, *, tenant_id: int, codigo: str) -> Cupom:
    cupom = (
        db.query(Cupom)
        .filter(Cupom.tenant_id == tenant_id, Cupom.codigo == codigo.strip().upper())
        .first()
    )
    if not cupom:
        raise CupomInvalido("Cupom não encontrado")
    if not cupom.ativo:
        raise CupomInvalido("Este cupom não está mais ativo")
    if cupom.valido_ate and cupom.valido_ate < datetime.utcnow():
        raise CupomInvalido("Este cupom expirou")
    if cupom.max_usos is not None and cupom.usos_atuais >= cupom.max_usos:
        raise CupomInvalido("Este cupom já atingiu o limite de usos")
    return cupom


def calcular_desconto(cupom: Cupom, preco_base: float) -> float:
    if cupom.tipo == TipoCupom.PERCENTUAL:
        desconto = preco_base * (float(cupom.valor) / 100)
    else:
        desconto = float(cupom.valor)
    return round(min(desconto, preco_base), 2)


def aplicar_cupom(db: Session, *, tenant_id: int, codigo: str, preco_base: float) -> tuple[Cupom, float]:
    """Valida o cupom, calcula o desconto e já incrementa `usos_atuais` —
    simplificação: o uso é contado na hora da compra (mesmo se for um Pix
    que depois expira sem confirmar), não fica esperando confirmação."""
    cupom = buscar_cupom_valido(db, tenant_id=tenant_id, codigo=codigo)
    desconto = calcular_desconto(cupom, preco_base)
    cupom.usos_atuais += 1
    db.add(cupom)
    return cupom, desconto
