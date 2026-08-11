from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import StatusFrete


class Frete(Base):
    """Envio de encomenda/carga — serviço independente da venda de
    passagem e do fretamento de ônibus. Pensado pra funcionar tanto numa
    viação quanto numa transportadora/caminhoneiro que não tem ônibus
    nenhum cadastrado: motorista e veículo ficam em texto livre, sem
    depender de app.models.onibus.Onibus."""

    __tablename__ = "fretes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    codigo_rastreio: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)

    remetente_nome: Mapped[str] = mapped_column(String(150), nullable=False)
    remetente_contato: Mapped[str | None] = mapped_column(String(100), nullable=True)
    destinatario_nome: Mapped[str] = mapped_column(String(150), nullable=False)
    destinatario_contato: Mapped[str | None] = mapped_column(String(100), nullable=True)

    descricao_carga: Mapped[str | None] = mapped_column(String(200), nullable=True)

    origem: Mapped[str] = mapped_column(String(150), nullable=False)
    destino: Mapped[str] = mapped_column(String(150), nullable=False)
    data_hora_coleta: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    data_hora_entrega_prevista: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    motorista_nome: Mapped[str | None] = mapped_column(String(150), nullable=True)
    veiculo_descricao: Mapped[str | None] = mapped_column(String(150), nullable=True)

    distancia_km: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    valor_por_km: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    valor_total: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    peso_kg: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    quantidade_volumes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valor_declarado: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    parceiro_id: Mapped[int | None] = mapped_column(ForeignKey("parceiros.id"), nullable=True)

    status: Mapped[StatusFrete] = mapped_column(SAEnum(StatusFrete), default=StatusFrete.SOLICITADO)
    icone_mapa: Mapped[str] = mapped_column(String(8), default="🚚")
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    posicoes = relationship(
        "PosicaoFrete", back_populates="frete", cascade="all, delete-orphan", order_by="PosicaoFrete.registrado_em"
    )


class PosicaoFrete(Base):
    """Uma leitura de GPS do trajeto da encomenda — mesmo padrão de
    app.models.fretamento.PosicaoFretamento."""

    __tablename__ = "posicoes_frete"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    frete_id: Mapped[int] = mapped_column(ForeignKey("fretes.id"), nullable=False)
    latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    registrado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    frete = relationship("Frete", back_populates="posicoes")
