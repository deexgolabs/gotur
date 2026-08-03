from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Viagem(Base):
    __tablename__ = "viagens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    rota_id: Mapped[int] = mapped_column(ForeignKey("rotas.id"), nullable=False)
    onibus_id: Mapped[int] = mapped_column(ForeignKey("onibus.id"), nullable=False)
    data_hora_partida: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    preco: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    rota = relationship("Rota")
    onibus = relationship("Onibus")
    poltronas = relationship("PoltronaViagem", back_populates="viagem", cascade="all, delete-orphan")
