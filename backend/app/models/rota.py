from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Rota(Base):
    __tablename__ = "rotas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    origem: Mapped[str] = mapped_column(String(100), nullable=False)
    destino: Mapped[str] = mapped_column(String(100), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    empresa = relationship("Empresa", back_populates="rotas")
    paradas = relationship("Parada", back_populates="rota", order_by="Parada.ordem", cascade="all, delete-orphan")
