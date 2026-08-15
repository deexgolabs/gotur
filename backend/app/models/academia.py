from datetime import date, datetime, time, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Time
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import FormaPagamento, StatusFatura, StatusMatricula, StatusPassagem, TipoMatricula, TipoReserva


class Turma(Base):
    """Template semanal de uma aula recorrente (spinning, pilates,
    crossfit) — não tem data própria, só dia da semana + horário; as
    instâncias datadas são geradas em OcorrenciaTurma. `instrutor` é texto
    livre, sem FK, mesmo espírito de Passagem.cliente_nome."""

    __tablename__ = "turmas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    dia_semana: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=segunda..6=domingo, igual date.weekday()
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    duracao_minutos: Mapped[int] = mapped_column(Integer, nullable=False)
    capacidade_vagas: Mapped[int] = mapped_column(Integer, nullable=False)
    instrutor: Mapped[str | None] = mapped_column(String(150), nullable=True)
    preco_avulso: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)  # null = não aceita drop-in
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    ocorrencias = relationship("OcorrenciaTurma", back_populates="turma", cascade="all, delete-orphan")


class OcorrenciaTurma(Base):
    """Uma instância datada de uma Turma, gerada por
    app.services.ocorrencias_turma.gerar_ocorrencias. `capacidade_vagas` é
    um snapshot do momento da geração — editar a Turma depois não muda
    retroativamente semanas já geradas. `vagas_ocupadas` não é coluna: é
    contada a partir de ReservaAula confirmada no router/schema."""

    __tablename__ = "ocorrencias_turma"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    turma_id: Mapped[int] = mapped_column(ForeignKey("turmas.id"), nullable=False)
    data_hora_inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    data_hora_fim: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    capacidade_vagas: Mapped[int] = mapped_column(Integer, nullable=False)
    cancelada: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    turma = relationship("Turma", back_populates="ocorrencias")


class Matricula(Base):
    """Relação contínua entre um cliente e uma academia — dá direito de
    reservar vaga em qualquer Turma ativa dessa empresa (não é por turma
    específica). Sem campo de vencimento: o ciclo mora na última
    FaturaMatricula, igual FaturaEmpresa faz pra Empresa."""

    __tablename__ = "matriculas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    cliente_usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    tipo: Mapped[TipoMatricula] = mapped_column(SAEnum(TipoMatricula), nullable=False)
    valor_mensalidade: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    aulas_por_ciclo: Mapped[int | None] = mapped_column(Integer, nullable=True)  # só pra PACOTE_AULAS
    aulas_utilizadas_ciclo_atual: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[StatusMatricula] = mapped_column(SAEnum(StatusMatricula), default=StatusMatricula.PENDENTE)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    cancelada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class FaturaMatricula(Base):
    """Fatura de mensalidade de uma Matricula — mesma forma de
    FaturaEmpresa, sem boleto (decisão de escopo: cobrança pequena e
    recorrente de consumidor final, o atrito do boleto não compensa)."""

    __tablename__ = "faturas_matricula"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    matricula_id: Mapped[int] = mapped_column(ForeignKey("matriculas.id"), nullable=False)
    cliente_usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    valor: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[StatusFatura] = mapped_column(SAEnum(StatusFatura), default=StatusFatura.PENDENTE)
    vencimento: Mapped[date] = mapped_column(Date, nullable=False)
    pago_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    forma_pagamento: Mapped[FormaPagamento | None] = mapped_column(SAEnum(FormaPagamento), nullable=True)
    gateway_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pix_copia_cola: Mapped[str | None] = mapped_column(String(300), nullable=True)
    pix_expira_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    matricula = relationship("Matricula")


class ReservaAula(Base):
    """Uma reserva de vaga numa OcorrenciaTurma — autorizada por uma
    Matricula ativa (tipo_reserva=MATRICULA) ou paga na hora sem matrícula
    (tipo_reserva=AVULSA, cliente_usuario_id pode ser nulo com
    cliente_nome/cliente_documento livres, igual Ingresso)."""

    __tablename__ = "reservas_aula"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    ocorrencia_turma_id: Mapped[int] = mapped_column(ForeignKey("ocorrencias_turma.id"), nullable=False)
    cliente_usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    cliente_nome: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cliente_documento: Mapped[str | None] = mapped_column(String(30), nullable=True)
    matricula_id: Mapped[int | None] = mapped_column(ForeignKey("matriculas.id"), nullable=True)
    tipo_reserva: Mapped[TipoReserva] = mapped_column(SAEnum(TipoReserva), nullable=False)
    status: Mapped[StatusPassagem] = mapped_column(SAEnum(StatusPassagem), default=StatusPassagem.CONFIRMADA)
    preco_pago: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)  # só avulsa
    forma_pagamento: Mapped[FormaPagamento | None] = mapped_column(SAEnum(FormaPagamento), nullable=True)  # só avulsa
    gateway_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    codigo: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    checkin_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    ocorrencia_turma = relationship("OcorrenciaTurma")
    matricula = relationship("Matricula")
