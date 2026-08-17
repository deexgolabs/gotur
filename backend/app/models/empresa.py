from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ModoCobranca, StatusAssinatura


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
    # Soft delete: some das listagens do super admin, mas os dados
    # continuam no banco (histórico fiscal das faturas já emitidas pra
    # essa empresa, entre outros motivos pra não apagar de verdade). Só
    # pode ser setado com a empresa já desativada (ver
    # app/routers/empresas.py::excluir_empresa).
    excluida_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    plano_id: Mapped[int | None] = mapped_column(ForeignKey("planos.id"), nullable=True)
    status_assinatura: Mapped[StatusAssinatura] = mapped_column(SAEnum(StatusAssinatura), default=StatusAssinatura.TRIAL)

    preco_km_fretamento: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)

    # Preço da mensalidade usado quando um cliente se matricula sozinho
    # pela loja (ver app/routers/matriculas.py::matricular_se_pela_loja) —
    # o cliente NUNCA escolhe o próprio preço; só o admin configura este
    # valor. Matrícula feita por staff continua podendo usar um valor
    # diferente por aluno (negociação caso a caso).
    preco_padrao_mensalidade_academia: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

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
    eventos_ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    academia_ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    # Programa de fidelidade: a cada N passagens confirmadas de um mesmo
    # cliente (com conta, cliente_usuario_id preenchido), gera automaticamente
    # um cupom pessoal de desconto (ver app/services/fidelidade.py).
    fidelidade_ativa: Mapped[bool] = mapped_column(Boolean, default=False)
    fidelidade_passagens_necessarias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fidelidade_desconto_percentual: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Programa de indicação: quando o indicado confirma a PRIMEIRA passagem
    # dele nessa empresa, indicado e indicador ganham cada um um cupom de
    # desconto (ver app/services/indicacao.py). Independente da fidelidade
    # acima (uma repete a cada N passagens, essa é única por indicação).
    indicacao_ativa: Mapped[bool] = mapped_column(Boolean, default=False)
    indicacao_desconto_percentual: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Mercado Pago da PRÓPRIA empresa (ver app/services/pagamento_provider.py)
    # — cada viação recebe na sua própria conta pelas passagens/fretes/
    # fretamentos que vende. Diferente de GOTUR_GATEWAY_API_KEY (global),
    # que é usado só pra cobrar a própria assinatura da empresa no GoTur.
    mercadopago_access_token: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mercadopago_public_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    modo_cobranca: Mapped[ModoCobranca] = mapped_column(SAEnum(ModoCobranca), default=ModoCobranca.AUTOMATICA, nullable=False)

    # Isenção da cobrança da PRÓPRIA assinatura no GoTur (diferente do
    # modo_cobranca acima, que é sobre o cliente da empresa) — pra contas
    # de teste/demonstração que o super admin não quer que gerem fatura
    # nem sejam suspensas por inadimplência. Ver app/services/faturamento.py
    # e app/services/assinatura.py.
    isento_cobranca: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

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

    @property
    def eventos_habilitado(self) -> bool:
        """Só usa eventos se o plano incluir E a empresa não tiver desligado."""
        permitido_pelo_plano = self.plano.modulo_eventos if self.plano else True
        return permitido_pelo_plano and self.eventos_ativo

    @property
    def academia_habilitado(self) -> bool:
        """Só usa academia se o plano incluir E a empresa não tiver desligado."""
        permitido_pelo_plano = self.plano.modulo_academia if self.plano else True
        return permitido_pelo_plano and self.academia_ativo

    @property
    def mercadopago_configurado(self) -> bool:
        return bool(self.mercadopago_access_token)

    # Diferenciais do plano Completo — sem toggle próprio (diferente dos
    # três acima), é só o plano que decide.
    @property
    def frota_habilitado(self) -> bool:
        return self.plano.modulo_frota if self.plano else True

    @property
    def motorista_habilitado(self) -> bool:
        return self.plano.modulo_motorista if self.plano else True

    @property
    def dre_habilitado(self) -> bool:
        return self.plano.modulo_dre if self.plano else True

    @property
    def white_label_habilitado(self) -> bool:
        return self.plano.modulo_white_label if self.plano else True

    @property
    def nfse_habilitado(self) -> bool:
        return self.plano.modulo_nfse if self.plano else True
