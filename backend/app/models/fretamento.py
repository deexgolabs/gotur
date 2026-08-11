from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import StatusFretamento


class Fretamento(Base):
    """Contrato de fretamento: aluguel do ônibus por um cliente/evento, fora
    da venda de passagem avulsa (ex: excursão, transporte de funcionários,
    viagem de turismo fechada)."""

    __tablename__ = "fretamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    codigo_rastreio: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)

    cliente_nome: Mapped[str] = mapped_column(String(150), nullable=False)
    cliente_documento: Mapped[str | None] = mapped_column(String(30), nullable=True)
    cliente_contato: Mapped[str | None] = mapped_column(String(100), nullable=True)

    origem: Mapped[str] = mapped_column(String(150), nullable=False)
    destino: Mapped[str] = mapped_column(String(150), nullable=False)
    data_hora_saida: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    data_hora_retorno_prevista: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    onibus_id: Mapped[int | None] = mapped_column(ForeignKey("onibus.id"), nullable=True)
    motorista_nome: Mapped[str | None] = mapped_column(String(150), nullable=True)

    distancia_km: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    valor_por_km: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    valor_total: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    status: Mapped[StatusFretamento] = mapped_column(SAEnum(StatusFretamento), default=StatusFretamento.ORCAMENTO)
    icone_mapa: Mapped[str] = mapped_column(String(8), default="🚌")
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    onibus = relationship("Onibus")
    posicoes = relationship(
        "PosicaoFretamento", back_populates="fretamento", cascade="all, delete-orphan", order_by="PosicaoFretamento.registrado_em"
    )


class PosicaoFretamento(Base):
    """Uma leitura de GPS do trajeto — enviada pelo celular do motorista
    enquanto o fretamento está em andamento. O rastro de pontos desenha o
    trajeto no mapa e permite calcular a distância percorrida."""

    __tablename__ = "posicoes_fretamento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fretamento_id: Mapped[int] = mapped_column(ForeignKey("fretamentos.id"), nullable=False)
    latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    registrado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    fretamento = relationship("Fretamento", back_populates="posicoes")
