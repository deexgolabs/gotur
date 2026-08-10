from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import StatusAssinatura


class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    cnpj: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    email_contato: Mapped[str] = mapped_column(String(150), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    plano_id: Mapped[int | None] = mapped_column(ForeignKey("planos.id"), nullable=True)
    status_assinatura: Mapped[StatusAssinatura] = mapped_column(SAEnum(StatusAssinatura), default=StatusAssinatura.TRIAL)

    preco_km_fretamento: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)

    usuarios = relationship("Usuario", back_populates="empresa")
    onibus = relationship("Onibus", back_populates="empresa")
    rotas = relationship("Rota", back_populates="empresa")
    plano = relationship("Plano", back_populates="empresas")
    faturas = relationship("FaturaEmpresa", back_populates="empresa", cascade="all, delete-orphan")
