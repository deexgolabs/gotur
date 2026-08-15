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

    # Quais módulos esse plano inclui. Uma empresa só consegue ligar um
    # módulo pra si (Empresa.fretamento_ativo/passagens_ativo) se o plano
    # dela permitir aqui.
    modulo_fretamento: Mapped[bool] = mapped_column(Boolean, default=True)
    modulo_passagens: Mapped[bool] = mapped_column(Boolean, default=True)
    modulo_frete: Mapped[bool] = mapped_column(Boolean, default=True)
    modulo_eventos: Mapped[bool] = mapped_column(Boolean, default=True)

    # Diferenciais do plano Completo — sem toggle próprio na Empresa (ao
    # contrário dos três acima): ou o plano inclui, ou não inclui. Ver
    # Empresa.frota_habilitado/motorista_habilitado/dre_habilitado/
    # white_label_habilitado/nfse_habilitado.
    modulo_frota: Mapped[bool] = mapped_column(Boolean, default=True)
    modulo_motorista: Mapped[bool] = mapped_column(Boolean, default=True)
    modulo_dre: Mapped[bool] = mapped_column(Boolean, default=True)
    modulo_white_label: Mapped[bool] = mapped_column(Boolean, default=True)
    modulo_nfse: Mapped[bool] = mapped_column(Boolean, default=True)

    empresas = relationship("Empresa", back_populates="plano")
