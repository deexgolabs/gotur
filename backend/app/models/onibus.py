from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import TipoOnibus


class Onibus(Base):
    __tablename__ = "onibus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    identificacao: Mapped[str] = mapped_column(String(50), nullable=False)  # placa ou número interno
    tipo: Mapped[TipoOnibus] = mapped_column(SAEnum(TipoOnibus), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    quilometragem_atual: Mapped[float | None] = mapped_column(Numeric(10, 1), nullable=True)

    empresa = relationship("Empresa", back_populates="onibus")
    poltronas = relationship("PoltronaOnibus", back_populates="onibus", cascade="all, delete-orphan")
    documentos = relationship("DocumentoOnibus", back_populates="onibus", cascade="all, delete-orphan")


class PoltronaOnibus(Base):
    __tablename__ = "poltronas_onibus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    onibus_id: Mapped[int] = mapped_column(ForeignKey("onibus.id"), nullable=False)
    numero: Mapped[str] = mapped_column(String(10), nullable=False)
    andar: Mapped[int] = mapped_column(Integer, default=1)
    fileira: Mapped[int] = mapped_column(Integer, nullable=False)
    coluna: Mapped[int] = mapped_column(Integer, nullable=False)
    categoria: Mapped[str] = mapped_column(String(30), default="padrao")
    multiplicador_preco: Mapped[float] = mapped_column(Numeric(4, 2), default=1.00)

    onibus = relationship("Onibus", back_populates="poltronas")
