from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import CategoriaPassageiro, FormaPagamento, StatusPassagem, TipoDocumento


class VenderPassagemRequest(BaseModel):
    poltrona_viagem_id: int
    cliente_nome: str
    cliente_documento: str
    cliente_telefone: str | None = None
    tipo_documento: TipoDocumento = TipoDocumento.CPF
    categoria_passageiro: CategoriaPassageiro = CategoriaPassageiro.COMUM
    forma_pagamento: FormaPagamento
    parada_origem_id: int | None = None
    parada_destino_id: int | None = None
    codigo_cupom: str | None = None
    parceiro_id: int | None = None

    # Só usados quando forma_pagamento == "cartao" — vêm do Card Payment
    # Brick do Mercado Pago rodando no navegador do cliente (o número do
    # cartão nunca chega até aqui, só o token já tokenizado). Ver
    # frontend/js/mercadopago-checkout.js.
    mp_token: str | None = None
    mp_payment_method_id: str | None = None
    mp_installments: int | None = None
    mp_payer_email: str | None = None


class PassagemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    viagem_id: int
    poltrona_viagem_id: int
    cliente_nome: str
    cliente_documento: str
    cliente_telefone: str | None = None
    tipo_documento: TipoDocumento = TipoDocumento.CPF
    categoria_passageiro: CategoriaPassageiro = CategoriaPassageiro.COMUM
    preco: float
    codigo_cupom: str | None = None
    parceiro_id: int | None = None
    status: StatusPassagem
    localizador: str
    criado_em: datetime
    reembolsado_em: datetime | None = None
    valor_reembolsado: float | None = None
    origem_trecho: str | None = None
    destino_trecho: str | None = None


class NfseOut(BaseModel):
    numero: str | None
    status: str
    url_pdf: str | None = None
    chave_acesso: str | None = None


class PassagemDetalheOut(PassagemOut):
    origem: str
    destino: str
    data_hora_partida: datetime
    numero_poltrona: str
    empresa_nome: str
    pode_avaliar: bool = False
    nota_avaliacao: int | None = None
