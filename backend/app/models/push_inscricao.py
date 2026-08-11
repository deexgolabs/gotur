from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import TipoRastreioPush


class PushInscricao(Base):
    """Inscrição de push notification (Web Push) de quem está acompanhando
    um fretamento ou frete pela tela pública de rastreio — sem exigir login.
    Quando o status muda, a empresa manda uma notificação real do navegador
    pra todo mundo inscrito naquele código, além do e-mail/WhatsApp."""

    __tablename__ = "push_inscricoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    tipo: Mapped[TipoRastreioPush] = mapped_column(SAEnum(TipoRastreioPush), nullable=False)
    objeto_id: Mapped[int] = mapped_column(Integer, nullable=False)

    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)

    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
