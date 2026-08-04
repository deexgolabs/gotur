from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RegistroAuditoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int | None
    usuario_nome: str | None = None
    acao: str
    entidade_tipo: str
    entidade_id: int | None
    detalhes: str | None
    criado_em: datetime
