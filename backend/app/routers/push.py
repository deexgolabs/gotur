from fastapi import APIRouter

from app.config import settings
from app.schemas.push import ChavePublicaPushOut

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/chave-publica", response_model=ChavePublicaPushOut)
def chave_publica():
    """Sem autenticação — o front usa isso pra inscrever o navegador no
    Push Manager (applicationServerKey). Sem GOTUR_VAPID_PUBLIC_KEY
    configurado, `chave_publica` vem None e o front esconde o botão de
    ativar notificações."""
    return ChavePublicaPushOut(chave_publica=settings.vapid_public_key)
