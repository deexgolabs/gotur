from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Parceiro(Base):
    """Agência/pessoa que vende passagem ou despacha frete em nome da
    empresa, normalmente embarcando num ponto intermediário da rota (ex:
    a empresa roda Aparecida de Goiânia -> Codó, e um parceiro em Palmas
    vende passagem pra quem embarca lá). Serve pra não misturar venda
    direta com venda via parceiro — comissão, conciliação e relatório
    ficam sempre rastreáveis por parceiro."""

    __tablename__ = "parceiros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)

    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    documento: Mapped[str | None] = mapped_column(String(30), nullable=True)
    contato: Mapped[str | None] = mapped_column(String(100), nullable=True)

    vende_passagem: Mapped[bool] = mapped_column(Boolean, default=True)
    despacha_frete: Mapped[bool] = mapped_column(Boolean, default=True)
    comissao_percentual: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    usuarios = relationship("Usuario", back_populates="parceiro")
