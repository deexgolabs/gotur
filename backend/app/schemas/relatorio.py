from datetime import datetime

from pydantic import BaseModel


class OcupacaoViagemOut(BaseModel):
    viagem_id: int
    origem: str
    destino: str
    data_hora_partida: datetime
    total_poltronas: int
    poltronas_vendidas: int
    percentual_ocupacao: float


class VendasResumoOut(BaseModel):
    periodo_inicio: datetime
    periodo_fim: datetime
    total_passagens: int
    total_arrecadado: float
    por_forma_pagamento: dict[str, float]


class VendasPorFuncionarioOut(BaseModel):
    usuario_id: int
    nome: str
    total_passagens: int
    total_arrecadado: float
