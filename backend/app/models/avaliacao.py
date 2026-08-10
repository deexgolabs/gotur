from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Avaliacao(Base):
    """Avaliação do cliente pós-viagem ou pós-fretamento (nota 1-5 +
    comentário opcional). Exatamente um entre `passagem_id`/`fretamento_id`
    é preenchido — cada um só pode ser avaliado uma vez (índice único)."""

    __tablename__ = "avaliacoes"
    __table_args__ = (
        CheckConstraint(
            "(passagem_id IS NOT NULL AND fretamento_id IS NULL) OR "
            "(passagem_id IS NULL AND fretamento_id IS NOT NULL)",
            name="ck_avaliacao_um_alvo",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    passagem_id: Mapped[int | None] = mapped_column(ForeignKey("passagens.id"), unique=True, nullable=True)
    fretamento_id: Mapped[int | None] = mapped_column(ForeignKey("fretamentos.id"), unique=True, nullable=True)
    nota: Mapped[int] = mapped_column(Integer, nullable=False)
    comentario: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    passagem = relationship("Passagem")
    fretamento = relationship("Fretamento")
