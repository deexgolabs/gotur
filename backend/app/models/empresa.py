from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
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
    telefone_contato: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Texto livre configurável pela empresa (política de cancelamento,
    # horário de atendimento, avisos) — exibido pro cliente na loja
    # white-label (ver LojaInfoOut).
    texto_loja: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    plano_id: Mapped[int | None] = mapped_column(ForeignKey("planos.id"), nullable=True)
    status_assinatura: Mapped[StatusAssinatura] = mapped_column(SAEnum(StatusAssinatura), default=StatusAssinatura.TRIAL)

    preco_km_fretamento: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)

    # White-label: cada empresa pode ter sua própria "loja" em /loja/{slug},
    # com nome/cor/logo próprios (ver app/routers/loja.py). `slug` é único
    # quando definido, mas fica nulo até o admin configurar em
    # Configurações — SQLite permite múltiplos NULLs num índice único.
    slug: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    cor_primaria: Mapped[str | None] = mapped_column(String(7), nullable=True)
    logo_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # A empresa liga/desliga o que usa, dentro do que o plano permite (ver
    # app/services/modulos.py) — uma viação que só faz fretamento pode
    # desligar a gestão de viagens, e vice-versa.
    fretamento_ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    passagens_ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    frete_ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    # Programa de fidelidade: a cada N passagens confirmadas de um mesmo
    # cliente (com conta, cliente_usuario_id preenchido), gera automaticamente
    # um cupom pessoal de desconto (ver app/services/fidelidade.py).
    fidelidade_ativa: Mapped[bool] = mapped_column(Boolean, default=False)
    fidelidade_passagens_necessarias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fidelidade_desconto_percentual: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    usuarios = relationship("Usuario", back_populates="empresa")
    onibus = relationship("Onibus", back_populates="empresa")
    rotas = relationship("Rota", back_populates="empresa")
    plano = relationship("Plano", back_populates="empresas")
    faturas = relationship("FaturaEmpresa", back_populates="empresa", cascade="all, delete-orphan")

    @property
    def logo_url(self) -> str | None:
        if not self.logo_filename:
            return None
        return f"/media/empresas/{self.id}/logo.png?v={self.logo_filename}"

    @property
    def fretamento_habilitado(self) -> bool:
        """Só usa fretamento se o plano incluir E a empresa não tiver desligado."""
        permitido_pelo_plano = self.plano.modulo_fretamento if self.plano else True
        return permitido_pelo_plano and self.fretamento_ativo

    @property
    def passagens_habilitado(self) -> bool:
        """Só usa gestão de viagens se o plano incluir E a empresa não tiver desligado."""
        permitido_pelo_plano = self.plano.modulo_passagens if self.plano else True
        return permitido_pelo_plano and self.passagens_ativo

    @property
    def frete_habilitado(self) -> bool:
        """Só usa frete se o plano incluir E a empresa não tiver desligado."""
        permitido_pelo_plano = self.plano.modulo_frete if self.plano else True
        return permitido_pelo_plano and self.frete_ativo
