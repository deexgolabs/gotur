from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PoltronaViagem(Base):
    """Representa uma poltrona física existindo numa viagem específica. A
    disponibilidade dela não é um status único — depende do trecho
    consultado, e é resolvida via OcupacaoPoltrona (ver
    app.models.ocupacao_poltrona)."""

    __tablename__ = "poltronas_viagem"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    viagem_id: Mapped[int] = mapped_column(ForeignKey("viagens.id"), nullable=False)
    poltrona_onibus_id: Mapped[int] = mapped_column(ForeignKey("poltronas_onibus.id"), nullable=False)

    viagem = relationship("Viagem", back_populates="poltronas")
    poltrona_onibus = relationship("PoltronaOnibus")
