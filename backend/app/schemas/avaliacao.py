from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AvaliarRequest(BaseModel):
    nota: int = Field(ge=1, le=5)
    comentario: str | None = None


class AvaliacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    passagem_id: int | None = None
    fretamento_id: int | None = None
    nota: int
    comentario: str | None = None
    criado_em: datetime
    cliente_nome: str | None = None
    origem: str | None = None
    destino: str | None = None


class ResumoAvaliacoesOut(BaseModel):
    total: int
    media: float | None = None
    avaliacoes: list[AvaliacaoOut]
