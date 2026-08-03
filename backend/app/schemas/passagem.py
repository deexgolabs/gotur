from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import FormaPagamento, StatusPassagem


class VenderPassagemRequest(BaseModel):
    poltrona_viagem_id: int
    cliente_nome: str
    cliente_documento: str
    forma_pagamento: FormaPagamento


class PassagemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    viagem_id: int
    poltrona_viagem_id: int
    cliente_nome: str
    cliente_documento: str
    preco: float
    status: StatusPassagem
    localizador: str
    criado_em: datetime


class PassagemDetalheOut(PassagemOut):
    origem: str
    destino: str
    data_hora_partida: datetime
    numero_poltrona: str
    empresa_nome: str
