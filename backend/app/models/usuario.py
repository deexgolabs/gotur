from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import UserRole


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), nullable=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), nullable=False)
    documento: Mapped[str | None] = mapped_column(String(30), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Só preenchido quando role == PARCEIRO: liga esse login ao cadastro
    # de parceiro (app.models.parceiro.Parceiro) cujas vendas ele pode ver.
    parceiro_id: Mapped[int | None] = mapped_column(ForeignKey("parceiros.id"), nullable=True)

    # Só preenchido quando role == MOTORISTA: liga esse login ao cadastro
    # de motorista (app.models.motorista.Motorista) — mesmo padrão do
    # parceiro_id acima. Sem isso, o motorista só existe como texto/registro
    # gerenciado pelo admin/funcionário, sem conseguir logar sozinho.
    motorista_id: Mapped[int | None] = mapped_column(ForeignKey("motoristas.id"), nullable=True)

    empresa = relationship("Empresa", back_populates="usuarios")
    parceiro = relationship("Parceiro", back_populates="usuarios")
    motorista = relationship("Motorista", back_populates="usuarios")
