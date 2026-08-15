from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field


class TurmaCreate(BaseModel):
    nome: str
    dia_semana: int = Field(ge=0, le=6, description="0=segunda .. 6=domingo")
    hora_inicio: time
    duracao_minutos: int = Field(gt=0)
    capacidade_vagas: int = Field(gt=0)
    instrutor: str | None = None
    preco_avulso: float | None = None


class TurmaUpdate(BaseModel):
    nome: str | None = None
    dia_semana: int | None = Field(default=None, ge=0, le=6)
    hora_inicio: time | None = None
    duracao_minutos: int | None = Field(default=None, gt=0)
    capacidade_vagas: int | None = Field(default=None, gt=0)
    instrutor: str | None = None
    preco_avulso: float | None = None


class TurmaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    dia_semana: int
    hora_inicio: time
    duracao_minutos: int
    capacidade_vagas: int
    instrutor: str | None = None
    preco_avulso: float | None = None
    ativa: bool


class OcorrenciaTurmaOut(BaseModel):
    id: int
    turma_id: int
    nome_turma: str
    data_hora_inicio: datetime
    data_hora_fim: datetime
    capacidade_vagas: int
    vagas_ocupadas: int
    cancelada: bool
    preco_avulso: float | None = None


class OcorrenciaTurmaUpdate(BaseModel):
    capacidade_vagas: int = Field(gt=0)
