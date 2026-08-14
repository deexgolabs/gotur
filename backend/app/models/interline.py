from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import CategoriaPassageiro, FormaPagamento, StatusPedidoInterline, StatusRepasse, TipoDocumento


class ConexaoInterline(Base):
    """Acordo entre duas empresas pra vender uma viagem combinada: a Rota A
    de uma empresa termina onde a Rota B da outra começa, e o cliente
    compra as duas pernas num único checkout. Cadastrada pelo super admin
    (ver app/routers/interline.py) — evita ter que construir uma UX de
    "empresa A propõe, empresa B aceita" já na v1; autoatendimento entre
    empresas fica pra depois."""

    __tablename__ = "conexoes_interline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rota_perna_a_id: Mapped[int] = mapped_column(ForeignKey("rotas.id"), nullable=False)
    rota_perna_b_id: Mapped[int] = mapped_column(ForeignKey("rotas.id"), nullable=False)
    # Denormalizado (cada Rota já tem tenant_id) só pra evitar join repetido
    # nas telas de "minhas conexões" de cada empresa.
    empresa_a_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    empresa_b_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    parada_conexao_nome: Mapped[str] = mapped_column(String(100), nullable=False)
    # Janela mínima entre a partida da perna A e a partida da perna B na
    # mesma data, usada na busca (ver app/services/interline.py) — v1 não
    # modela horário de chegada estimado da perna A, só usa essa folga.
    minutos_conexao_minima: Mapped[int] = mapped_column(Integer, default=30)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    rota_perna_a = relationship("Rota", foreign_keys=[rota_perna_a_id])
    rota_perna_b = relationship("Rota", foreign_keys=[rota_perna_b_id])
    empresa_a = relationship("Empresa", foreign_keys=[empresa_a_id])
    empresa_b = relationship("Empresa", foreign_keys=[empresa_b_id])


class PedidoInterline(Base):
    """A "sacola" que amarra as duas Passagens (uma por empresa) de uma
    compra interline. Cada perna continua sendo uma Passagem normal,
    gerada pela mesma `_criar_passagem_confirmada` de sempre
    (app/routers/passagens.py) — este registro só existe pra saber que as
    duas pertencem à mesma compra do cliente."""

    __tablename__ = "pedidos_interline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conexao_id: Mapped[int] = mapped_column(ForeignKey("conexoes_interline.id"), nullable=False)

    # Dados da compra em andamento — precisam ficar guardados aqui (e não só
    # na Passagem, que só existe depois de confirmado) porque, com Pix
    # pendente, é a partir deles que as duas Passagens são criadas quando o
    # pagamento cai (ver confirmar_pedido_interline em
    # app/routers/interline.py). Espelha os mesmos campos de
    # PedidoPagamento, só que duplicados por perna.
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    cliente_nome: Mapped[str] = mapped_column(String(150), nullable=False)
    cliente_documento: Mapped[str] = mapped_column(String(30), nullable=False)
    cliente_telefone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tipo_documento: Mapped[TipoDocumento] = mapped_column(SAEnum(TipoDocumento), default=TipoDocumento.CPF)
    categoria_passageiro: Mapped[CategoriaPassageiro] = mapped_column(SAEnum(CategoriaPassageiro), default=CategoriaPassageiro.COMUM)
    forma_pagamento: Mapped[FormaPagamento] = mapped_column(SAEnum(FormaPagamento), nullable=False)

    viagem_perna_a_id: Mapped[int] = mapped_column(ForeignKey("viagens.id"), nullable=False)
    poltrona_perna_a_id: Mapped[int] = mapped_column(ForeignKey("poltronas_viagem.id"), nullable=False)
    parada_origem_a_id: Mapped[int] = mapped_column(ForeignKey("paradas.id"), nullable=False)
    parada_destino_a_id: Mapped[int] = mapped_column(ForeignKey("paradas.id"), nullable=False)

    viagem_perna_b_id: Mapped[int] = mapped_column(ForeignKey("viagens.id"), nullable=False)
    poltrona_perna_b_id: Mapped[int] = mapped_column(ForeignKey("poltronas_viagem.id"), nullable=False)
    parada_origem_b_id: Mapped[int] = mapped_column(ForeignKey("paradas.id"), nullable=False)
    parada_destino_b_id: Mapped[int] = mapped_column(ForeignKey("paradas.id"), nullable=False)

    passagem_perna_a_id: Mapped[int | None] = mapped_column(ForeignKey("passagens.id"), nullable=True)
    passagem_perna_b_id: Mapped[int | None] = mapped_column(ForeignKey("passagens.id"), nullable=True)
    valor_perna_a: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    valor_perna_b: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    valor_total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[StatusPedidoInterline] = mapped_column(
        SAEnum(StatusPedidoInterline), default=StatusPedidoInterline.PENDENTE_PAGAMENTO
    )
    # Preenchidos só quando o pagamento (do valor total, cobrado uma vez da
    # empresa vendedora) fica pendente via Pix — mesmo padrão do
    # PedidoPagamento de uma perna só (app/models/pedido_pagamento.py).
    pix_copia_cola: Mapped[str | None] = mapped_column(String(300), nullable=True)
    pix_expira_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    gateway_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    conexao = relationship("ConexaoInterline")
    passagem_perna_a = relationship("Passagem", foreign_keys=[passagem_perna_a_id])
    passagem_perna_b = relationship("Passagem", foreign_keys=[passagem_perna_b_id])


class AcertoInterline(Base):
    """Dívida gerada por uma venda interline: a empresa que vendeu (recebeu
    o pagamento do cliente inteiro) fica devendo pra empresa que operou a
    perna B a parte dela. Liquidado manualmente por fora do sistema, mesmo
    espírito do RepasseParceiro (app/models/repasse_parceiro.py) — só que
    aqui é por venda, não por período acumulado (dá pra evoluir pra acúmulo
    por período depois, se o volume justificar)."""

    __tablename__ = "acertos_interline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pedido_interline_id: Mapped[int] = mapped_column(ForeignKey("pedidos_interline.id"), nullable=False)
    empresa_devedora_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    empresa_credora_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    valor_devido: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[StatusRepasse] = mapped_column(SAEnum(StatusRepasse), default=StatusRepasse.PENDENTE)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    pago_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    pedido_interline = relationship("PedidoInterline")
    empresa_devedora = relationship("Empresa", foreign_keys=[empresa_devedora_id])
    empresa_credora = relationship("Empresa", foreign_keys=[empresa_credora_id])
