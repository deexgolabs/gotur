from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import FormaPagamento


class Pagamento(Base):
    """Registro manual do pagamento no v1. `gateway_ref` fica pronto para
    quando um gateway de pagamento real for integrado (Fase 5)."""

    __tablename__ = "pagamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    passagem_id: Mapped[int] = mapped_column(ForeignKey("passagens.id"), nullable=False, unique=True)
    forma_pagamento: Mapped[FormaPagamento] = mapped_column(SAEnum(FormaPagamento), nullable=False)
    valor: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    gateway_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    passagem = relationship("Passagem", back_populates="pagamento")
