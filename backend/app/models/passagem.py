from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import StatusPassagem


class Passagem(Base):
    __tablename__ = "passagens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    viagem_id: Mapped[int] = mapped_column(ForeignKey("viagens.id"), nullable=False)
    poltrona_viagem_id: Mapped[int] = mapped_column(ForeignKey("poltronas_viagem.id"), nullable=False)
    parada_origem_id: Mapped[int] = mapped_column(ForeignKey("paradas.id"), nullable=False)
    parada_destino_id: Mapped[int] = mapped_column(ForeignKey("paradas.id"), nullable=False)
    cliente_usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    cliente_nome: Mapped[str] = mapped_column(String(150), nullable=False)
    cliente_documento: Mapped[str] = mapped_column(String(30), nullable=False)
    vendido_por_usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    preco: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[StatusPassagem] = mapped_column(SAEnum(StatusPassagem), default=StatusPassagem.CONFIRMADA)
    localizador: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    checkin_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    viagem = relationship("Viagem")
    poltrona_viagem = relationship("PoltronaViagem")
    parada_origem = relationship("Parada", foreign_keys=[parada_origem_id])
    parada_destino = relationship("Parada", foreign_keys=[parada_destino_id])
    pagamento = relationship("Pagamento", back_populates="passagem", uselist=False, cascade="all, delete-orphan")

    @property
    def reembolsado_em(self) -> datetime | None:
        return self.pagamento.reembolsado_em if self.pagamento else None

    @property
    def valor_reembolsado(self) -> float | None:
        return float(self.pagamento.valor_reembolsado) if self.pagamento and self.pagamento.valor_reembolsado else None

    @property
    def origem_trecho(self) -> str | None:
        return self.parada_origem.nome if self.parada_origem else None

    @property
    def destino_trecho(self) -> str | None:
        return self.parada_destino.nome if self.parada_destino else None
