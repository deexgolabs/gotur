from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import TipoCupom


class Cupom(Base):
    """Cupom de desconto aplicável na compra de passagem — percentual (ex:
    10% off) ou valor fixo (ex: R$ 20 off). `usos_atuais` é incrementado a
    cada aplicação bem-sucedida; `max_usos` None significa sem limite."""

    __tablename__ = "cupons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    codigo: Mapped[str] = mapped_column(String(30), nullable=False)

    tipo: Mapped[TipoCupom] = mapped_column(SAEnum(TipoCupom), nullable=False)
    valor: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    valido_ate: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    max_usos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usos_atuais: Mapped[int] = mapped_column(Integer, default=0)

    # Preenchido quando o cupom foi gerado pelo programa de fidelidade —
    # só esse cliente pode usar (ver app/services/fidelidade.py e
    # app/services/cupom.py). Nulo = cupom geral, qualquer cliente usa.
    cliente_usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)

    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
