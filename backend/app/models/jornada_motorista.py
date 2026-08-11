from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import TipoViagemJornada


class JornadaMotorista(Base):
    """Início/fim de jornada de um motorista num trajeto (viagem, fretamento
    ou frete) — motorista ainda é texto livre (não é uma entidade própria
    no sistema), o mesmo padrão já usado em `motorista_nome` nesses três
    modelos. Serve pra empresa acompanhar a carga horária e ficar de olho
    no limite da Lei do Motorista (13.103/2015) — o sistema só avisa
    quando passa de 8h nas últimas 24h, não bloqueia nada."""

    __tablename__ = "jornadas_motorista"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)

    motorista_nome: Mapped[str] = mapped_column(String(150), nullable=False)
    tipo_viagem: Mapped[TipoViagemJornada] = mapped_column(SAEnum(TipoViagemJornada), nullable=False)
    referencia_id: Mapped[int] = mapped_column(Integer, nullable=False)

    inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fim: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
