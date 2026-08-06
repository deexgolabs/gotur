from sqlalchemy import Boolean, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Plano(Base):
    """Plano de assinatura da plataforma (o que a VIAÇÃO paga pra usar o
    GoTur — não confundir com o preço da passagem, que é outra coisa)."""

    __tablename__ = "planos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(50), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    preco_mensal: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    max_onibus: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_funcionarios: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_viagens_mes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    empresas = relationship("Empresa", back_populates="plano")
