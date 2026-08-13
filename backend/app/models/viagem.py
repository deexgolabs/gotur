from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
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
    motorista_nome: Mapped[str | None] = mapped_column(String(150), nullable=True)
    motorista_id: Mapped[int | None] = mapped_column(ForeignKey("motoristas.id"), nullable=True)

    # Código curto pro cliente acompanhar o ônibus ao vivo em /rastrear-viagem
    # (ver PosicaoViagem) — nullable porque viagens criadas antes desse
    # recurso não têm um ainda; é gerado lazy na primeira consulta que
    # precisar dele (mesmo padrão do slug de white-label da Empresa).
    codigo_rastreio: Mapped[str | None] = mapped_column(String(12), unique=True, nullable=True)

    rota = relationship("Rota")
    onibus = relationship("Onibus")
    motorista = relationship("Motorista")
    poltronas = relationship("PoltronaViagem", back_populates="viagem", cascade="all, delete-orphan")
    posicoes = relationship(
        "PosicaoViagem", back_populates="viagem", cascade="all, delete-orphan", order_by="PosicaoViagem.registrado_em"
    )


class PosicaoViagem(Base):
    """Uma leitura de GPS do trajeto da viagem — enviada pelo celular de
    quem está compartilhando localização enquanto ela está em andamento.
    Mesmo padrão de PosicaoFretamento/PosicaoFrete."""

    __tablename__ = "posicoes_viagem"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    viagem_id: Mapped[int] = mapped_column(ForeignKey("viagens.id"), nullable=False)
    latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    registrado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    viagem = relationship("Viagem", back_populates="posicoes")
