from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import TipoViagemJornada


class ChecklistViagem(Base):
    """Checklist pré-viagem preenchido pelo motorista (pneus, óleo,
    combustível) — mesmo padrão polimórfico de `JornadaMotorista`
    (tipo_viagem + referencia_id cobre viagem, fretamento e frete).
    Cada checklist é um novo registro (histórico preservado), preenchido
    junto do botão "Jornada" que já existe nas 3 telas."""

    __tablename__ = "checklists_viagem"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)

    motorista_nome: Mapped[str] = mapped_column(String(150), nullable=False)
    tipo_viagem: Mapped[TipoViagemJornada] = mapped_column(SAEnum(TipoViagemJornada), nullable=False)
    referencia_id: Mapped[int] = mapped_column(Integer, nullable=False)

    pneus_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    oleo_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    combustivel_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
