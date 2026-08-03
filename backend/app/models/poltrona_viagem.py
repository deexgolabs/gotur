from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import StatusPoltrona


class PoltronaViagem(Base):
    __tablename__ = "poltronas_viagem"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    viagem_id: Mapped[int] = mapped_column(ForeignKey("viagens.id"), nullable=False)
    poltrona_onibus_id: Mapped[int] = mapped_column(ForeignKey("poltronas_onibus.id"), nullable=False)
    status: Mapped[StatusPoltrona] = mapped_column(SAEnum(StatusPoltrona), default=StatusPoltrona.LIVRE)
    hold_expira_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    hold_usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    bloqueio_motivo: Mapped[str | None] = mapped_column(String(200), nullable=True)

    viagem = relationship("Viagem", back_populates="poltronas")
    poltrona_onibus = relationship("PoltronaOnibus")
