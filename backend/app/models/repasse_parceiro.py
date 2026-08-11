from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import StatusRepasse


class RepasseParceiro(Base):
    """Fecha o ciclo da comissão do parceiro: cada registro apura passagens
    e fretes vendidos por ele num período (desde o último repasse gerado,
    ou desde o cadastro do parceiro no primeiro) e vira um "a pagar" que o
    admin marca como pago depois de transferir por fora do sistema."""

    __tablename__ = "repasses_parceiro"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    parceiro_id: Mapped[int] = mapped_column(ForeignKey("parceiros.id"), nullable=False)

    periodo_inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    periodo_fim: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    total_passagens: Mapped[int] = mapped_column(Integer, default=0)
    valor_passagens: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    total_fretes: Mapped[int] = mapped_column(Integer, default=0)
    valor_fretes: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    # Percentual "congelado" no momento da geração — se o admin mudar a
    # comissão do parceiro depois, repasses já gerados não são afetados.
    comissao_percentual: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    valor_comissao: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    status: Mapped[StatusRepasse] = mapped_column(SAEnum(StatusRepasse), default=StatusRepasse.PENDENTE)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    pago_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    parceiro = relationship("Parceiro")
