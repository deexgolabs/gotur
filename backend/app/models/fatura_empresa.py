from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import StatusFatura


class FaturaEmpresa(Base):
    """Cobrança da assinatura da plataforma para uma empresa (o que a
    viação paga pra usar o Vion). Gerada manualmente pelo super admin no
    v1 — pronta para virar uma tarefa agendada (cron) mais pra frente."""

    __tablename__ = "faturas_empresa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    plano_id: Mapped[int] = mapped_column(ForeignKey("planos.id"), nullable=False)
    valor: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[StatusFatura] = mapped_column(SAEnum(StatusFatura), default=StatusFatura.PENDENTE)
    vencimento: Mapped[date] = mapped_column(Date, nullable=False)
    pago_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    gateway_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pix_copia_cola: Mapped[str | None] = mapped_column(String(300), nullable=True)
    pix_expira_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    empresa = relationship("Empresa", back_populates="faturas")
    plano = relationship("Plano")
