from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import FormaPagamento, StatusPassagem


class VenderPassagemRequest(BaseModel):
    poltrona_viagem_id: int
    cliente_nome: str
    cliente_documento: str
    forma_pagamento: FormaPagamento
    parada_origem_id: int | None = None
    parada_destino_id: int | None = None
    codigo_cupom: str | None = None


class PassagemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    viagem_id: int
    poltrona_viagem_id: int
    cliente_nome: str
    cliente_documento: str
    preco: float
    codigo_cupom: str | None = None
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
