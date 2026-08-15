from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import FormaPagamento, StatusPassagem, StatusPedidoPagamento, StatusPoltrona


class Local(Base):
    """Um espaço com lugar marcado (cinema, teatro, casa de show, estádio)
    — equivalente ao Onibus do módulo de passagens, mas sem nada
    específico de veículo."""

    __tablename__ = "locais"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    endereco: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    assentos = relationship("AssentoLocal", back_populates="local", cascade="all, delete-orphan")


class AssentoLocal(Base):
    """Um assento físico do Local — equivalente a PoltronaOnibus. `setor`
    substitui o "andar" do ônibus (não faz sentido pra teatro/cinema):
    texto livre tipo "plateia", "balcão", "setor A"."""

    __tablename__ = "assentos_local"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    local_id: Mapped[int] = mapped_column(ForeignKey("locais.id"), nullable=False)
    numero: Mapped[str] = mapped_column(String(10), nullable=False)
    fileira: Mapped[int] = mapped_column(Integer, nullable=False)
    coluna: Mapped[int] = mapped_column(Integer, nullable=False)
    setor: Mapped[str | None] = mapped_column(String(50), nullable=True)
    categoria: Mapped[str] = mapped_column(String(30), default="padrao")
    multiplicador_preco: Mapped[float] = mapped_column(Numeric(4, 2), default=1.00)

    local = relationship("Local", back_populates="assentos")


class Sessao(Base):
    """Uma sessão/apresentação/jogo com horário marcado num Local —
    equivalente a Viagem, bem mais simples (sem rota, ônibus ou GPS: o
    local não se move e não tem trecho intermediário)."""

    __tablename__ = "sessoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    local_id: Mapped[int] = mapped_column(ForeignKey("locais.id"), nullable=False)
    nome_evento: Mapped[str] = mapped_column(String(150), nullable=False)
    data_hora: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    preco: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    local = relationship("Local")
    assentos = relationship("AssentoSessao", back_populates="sessao", cascade="all, delete-orphan")


class AssentoSessao(Base):
    """Um AssentoLocal instanciado pra uma Sessao específica — equivalente
    a PoltronaViagem, mas com status DIRETO em vez do ledger de intervalo
    por trecho (OcupacaoPoltrona): uma sessão de evento não tem paradas
    intermediárias, então não existe "vender pra metade do trajeto" —
    um assento tem um único estado por sessão."""

    __tablename__ = "assentos_sessao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sessao_id: Mapped[int] = mapped_column(ForeignKey("sessoes.id"), nullable=False)
    assento_local_id: Mapped[int] = mapped_column(ForeignKey("assentos_local.id"), nullable=False)
    status: Mapped[StatusPoltrona] = mapped_column(SAEnum(StatusPoltrona), default=StatusPoltrona.LIVRE)
    hold_usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    hold_expira_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ingresso_id: Mapped[int | None] = mapped_column(ForeignKey("ingressos.id"), nullable=True)

    sessao = relationship("Sessao", back_populates="assentos")
    assento_local = relationship("AssentoLocal")


class Ingresso(Base):
    """Um bilhete de evento confirmado — equivalente a Passagem, com os
    campos de pagamento embutidos direto aqui (forma_pagamento,
    gateway_ref, reembolso) em vez de uma tabela Pagamento separada: a
    `Pagamento` existente tem FK obrigatória pra passagens.id, então
    reaproveitá-la exigiria torná-la polimórfica — risco desnecessário
    num código de venda de passagem já em produção. Mantém Eventos 100%
    independente, mesmo espírito do módulo de Frete."""

    __tablename__ = "ingressos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    sessao_id: Mapped[int] = mapped_column(ForeignKey("sessoes.id"), nullable=False)
    assento_sessao_id: Mapped[int] = mapped_column(ForeignKey("assentos_sessao.id"), nullable=False)
    cliente_usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    cliente_nome: Mapped[str] = mapped_column(String(150), nullable=False)
    cliente_documento: Mapped[str] = mapped_column(String(30), nullable=False)
    vendido_por_usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    preco: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    forma_pagamento: Mapped[FormaPagamento] = mapped_column(SAEnum(FormaPagamento), nullable=False)
    gateway_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[StatusPassagem] = mapped_column(SAEnum(StatusPassagem), default=StatusPassagem.CONFIRMADA)
    codigo: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    checkin_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    valor_reembolsado: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    motivo_reembolso: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reembolsado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    sessao = relationship("Sessao")
    assento_sessao = relationship("AssentoSessao", foreign_keys=[assento_sessao_id])


class PedidoIngressoPendente(Base):
    """Compra de ingresso com Pix ainda não confirmado — equivalente a
    PedidoPagamento, sem os campos de trecho/parada (não existem pra
    evento)."""

    __tablename__ = "pedidos_ingresso_pendente"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    sessao_id: Mapped[int] = mapped_column(ForeignKey("sessoes.id"), nullable=False)
    assento_sessao_id: Mapped[int] = mapped_column(ForeignKey("assentos_sessao.id"), nullable=False)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    cliente_nome: Mapped[str] = mapped_column(String(150), nullable=False)
    cliente_documento: Mapped[str] = mapped_column(String(30), nullable=False)
    forma_pagamento: Mapped[FormaPagamento] = mapped_column(SAEnum(FormaPagamento), nullable=False)
    valor: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    pix_copia_cola: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[StatusPedidoPagamento] = mapped_column(SAEnum(StatusPedidoPagamento), default=StatusPedidoPagamento.PENDENTE)
    ingresso_id: Mapped[int | None] = mapped_column(ForeignKey("ingressos.id"), nullable=True)
    gateway_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expira_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    sessao = relationship("Sessao")
    assento_sessao = relationship("AssentoSessao", foreign_keys=[assento_sessao_id])
