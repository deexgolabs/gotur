from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import TipoOcupacao


class OcupacaoPoltrona(Base):
    """"Livro-razão" de ocupação de uma poltrona numa viagem, por trecho.

    Em vez de uma poltrona ter um único status para a viagem inteira, cada
    linha aqui representa um intervalo [parada_origem_ordem,
    parada_destino_ordem) ocupado por um hold temporário, um bloqueio
    administrativo ou uma venda confirmada. Duas linhas da mesma poltrona só
    podem coexistir se os intervalos não se sobrepõem — assim a mesma
    poltrona física pode ser vendida para dois passageiros em trechos
    diferentes da mesma viagem.
    """

    __tablename__ = "ocupacoes_poltrona"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    poltrona_viagem_id: Mapped[int] = mapped_column(ForeignKey("poltronas_viagem.id"), nullable=False)
    tipo: Mapped[TipoOcupacao] = mapped_column(SAEnum(TipoOcupacao), nullable=False)
    parada_origem_ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    parada_destino_ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    expira_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    passagem_id: Mapped[int | None] = mapped_column(ForeignKey("passagens.id"), nullable=True)
    motivo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    poltrona_viagem = relationship("PoltronaViagem")
