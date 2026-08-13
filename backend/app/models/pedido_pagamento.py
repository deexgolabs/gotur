from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import CategoriaPassageiro, FormaPagamento, StatusPedidoPagamento, TipoDocumento


class PedidoPagamento(Base):
    """Cobrança Pix pendente de confirmação (compra online do cliente).

    Enquanto o Pix não é confirmado, a passagem ainda não existe — só o
    assento fica reservado (hold) esperando o pagamento cair. Quando a
    confirmação chega (simulada no v1, webhook do gateway real no futuro),
    a passagem é criada e o pedido vira CONFIRMADO."""

    __tablename__ = "pedidos_pagamento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    viagem_id: Mapped[int] = mapped_column(ForeignKey("viagens.id"), nullable=False)
    poltrona_viagem_id: Mapped[int] = mapped_column(ForeignKey("poltronas_viagem.id"), nullable=False)
    parada_origem_id: Mapped[int] = mapped_column(ForeignKey("paradas.id"), nullable=False)
    parada_destino_id: Mapped[int] = mapped_column(ForeignKey("paradas.id"), nullable=False)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    cliente_nome: Mapped[str] = mapped_column(String(150), nullable=False)
    cliente_documento: Mapped[str] = mapped_column(String(30), nullable=False)
    forma_pagamento: Mapped[FormaPagamento] = mapped_column(SAEnum(FormaPagamento), nullable=False)
    valor: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    codigo_cupom: Mapped[str | None] = mapped_column(String(30), nullable=True)
    parceiro_id: Mapped[int | None] = mapped_column(ForeignKey("parceiros.id"), nullable=True)
    cliente_telefone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tipo_documento: Mapped[TipoDocumento] = mapped_column(SAEnum(TipoDocumento), default=TipoDocumento.CPF)
    categoria_passageiro: Mapped[CategoriaPassageiro] = mapped_column(SAEnum(CategoriaPassageiro), default=CategoriaPassageiro.COMUM)
    pix_copia_cola: Mapped[str] = mapped_column(String(300), nullable=False)
    # ID do pagamento no Mercado Pago (quando cobrado via gateway real) —
    # é o que o webhook usa pra saber qual pedido confirmar quando o Pix
    # cai (ver app/routers/webhooks.py). Em modo simulado fica nulo até a
    # confirmação (que gera "SIMULADO-{id}" na hora de confirmar).
    gateway_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[StatusPedidoPagamento] = mapped_column(
        SAEnum(StatusPedidoPagamento), default=StatusPedidoPagamento.PENDENTE, nullable=False
    )
    passagem_id: Mapped[int | None] = mapped_column(ForeignKey("passagens.id"), nullable=True)
    expira_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    viagem = relationship("Viagem")
    poltrona_viagem = relationship("PoltronaViagem")
    passagem = relationship("Passagem")
