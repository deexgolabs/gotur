from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import CategoriaPassageiro, FormaPagamento, StatusPedidoInterline, StatusRepasse, TipoDocumento


class RotaParaConexaoOut(BaseModel):
    """Rota de qualquer empresa, pro super admin escolher as duas pernas
    ao cadastrar uma ConexaoInterline (não existe um `GET /rotas` que
    atravesse tenants — só faz sentido aqui)."""

    id: int
    empresa_id: int
    empresa_nome: str
    origem: str
    destino: str


class CriarConexaoInterlineRequest(BaseModel):
    rota_perna_a_id: int
    rota_perna_b_id: int
    parada_conexao_nome: str
    minutos_conexao_minima: int = 30


class ConexaoInterlineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rota_perna_a_id: int
    rota_perna_b_id: int
    empresa_a_id: int
    empresa_b_id: int
    empresa_a_nome: str | None = None
    empresa_b_nome: str | None = None
    origem_a: str | None = None
    destino_a: str | None = None
    origem_b: str | None = None
    destino_b: str | None = None
    parada_conexao_nome: str
    minutos_conexao_minima: int
    ativo: bool
    criado_em: datetime


class OpcaoInterlineOut(BaseModel):
    """Um par de viagens compatível encontrado por `GET /interline/buscar`
    — a "sacola" (PedidoInterline) só é criada de fato quando o cliente
    decide comprar."""

    conexao_id: int
    parada_conexao_nome: str
    empresa_a_nome: str
    empresa_b_nome: str
    viagem_perna_a_id: int
    viagem_perna_b_id: int
    data_hora_partida_a: datetime
    data_hora_partida_b: datetime
    valor_perna_a: float
    valor_perna_b: float
    valor_total: float


class ComprarInterlineRequest(BaseModel):
    conexao_id: int
    viagem_perna_a_id: int
    poltrona_perna_a_id: int
    viagem_perna_b_id: int
    poltrona_perna_b_id: int

    cliente_nome: str
    cliente_documento: str
    cliente_telefone: str | None = None
    tipo_documento: TipoDocumento = TipoDocumento.CPF
    categoria_passageiro: CategoriaPassageiro = CategoriaPassageiro.COMUM
    forma_pagamento: FormaPagamento

    # Só usados quando forma_pagamento == "cartao" (Card Payment Brick,
    # ver frontend/js/mercadopago-checkout.js).
    mp_token: str | None = None
    mp_payment_method_id: str | None = None
    mp_installments: int | None = None
    mp_payer_email: str | None = None


class PedidoInterlineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conexao_id: int
    status: StatusPedidoInterline
    valor_perna_a: float
    valor_perna_b: float
    valor_total: float
    passagem_perna_a_id: int | None = None
    passagem_perna_b_id: int | None = None
    pix_copia_cola: str | None = None
    pix_expira_em: datetime | None = None
    criado_em: datetime
    # True quando não há gateway real configurado pra empresa vendedora —
    # mesmo controle usado em PedidoPagamentoOut/FaturaOut pra decidir se a
    # tela mostra o botão de confirmação manual.
    pagamento_simulado: bool = True


class CompraInterlineResponse(BaseModel):
    passagem_perna_a_id: int | None = None
    passagem_perna_b_id: int | None = None
    localizador_perna_a: str | None = None
    localizador_perna_b: str | None = None
    pedido_interline: PedidoInterlineOut | None = None


class AcertoInterlineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pedido_interline_id: int
    empresa_devedora_id: int
    empresa_credora_id: int
    empresa_devedora_nome: str | None = None
    empresa_credora_nome: str | None = None
    valor_devido: float
    status: StatusRepasse
    criado_em: datetime
    pago_em: datetime | None = None
