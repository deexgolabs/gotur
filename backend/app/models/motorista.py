from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import CategoriaCNH


class Motorista(Base):
    """Motorista cadastrado pela empresa — vinculável em viagens,
    fretamentos e fretes (ver `motorista_id` nesses três modelos). Antes
    disso, motorista era só um campo de texto livre repetido em cada
    formulário; agora vira um cadastro próprio, reaproveitável."""

    __tablename__ = "motoristas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)

    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    cnh: Mapped[str | None] = mapped_column(String(20), nullable=True)
    categoria_cnh: Mapped[CategoriaCNH | None] = mapped_column(SAEnum(CategoriaCNH), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    usuarios = relationship("Usuario", back_populates="motorista")
