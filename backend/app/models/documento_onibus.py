from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import TipoDocumentoOnibus


class DocumentoOnibus(Base):
    """Item com data de vencimento controlado por ônibus — CRLV, seguro,
    revisão preventiva por data, ou qualquer outro documento. Cada renovação
    é um novo registro (o histórico fica todo visível), não uma edição in
    loco do vencimento anterior."""

    __tablename__ = "documentos_onibus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    onibus_id: Mapped[int] = mapped_column(ForeignKey("onibus.id"), nullable=False)

    tipo: Mapped[TipoDocumentoOnibus] = mapped_column(SAEnum(TipoDocumentoOnibus), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(200), nullable=True)
    data_vencimento: Mapped[date] = mapped_column(Date, nullable=False)

    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    onibus = relationship("Onibus", back_populates="documentos")
