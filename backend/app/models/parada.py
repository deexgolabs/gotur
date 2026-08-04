from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Parada(Base):
    """Um ponto de parada de uma rota, em ordem crescente (0 = origem final,
    maior ordem = destino final). `peso_proximo` é o peso do trecho ENTRE
    esta parada e a próxima (proporcional ao preço da viagem) — None na
    última parada, que não tem "próximo trecho"."""

    __tablename__ = "paradas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rota_id: Mapped[int] = mapped_column(ForeignKey("rotas.id"), nullable=False)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    peso_proximo: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    rota = relationship("Rota", back_populates="paradas")
