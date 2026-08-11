from pydantic import BaseModel


class PushChaves(BaseModel):
    p256dh: str
    auth: str


class InscricaoPushRequest(BaseModel):
    endpoint: str
    keys: PushChaves


class ChavePublicaPushOut(BaseModel):
    chave_publica: str | None = None
