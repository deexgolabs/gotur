"""Push notification real (Web Push), self-hosted via VAPID — sem depender
de Firebase ou qualquer serviço pago. Funciona em qualquer navegador que
suporte a Push API (Chrome, Edge, Firefox; Safari a partir do iOS 16.4).

Sem GOTUR_VAPID_PUBLIC_KEY/GOTUR_VAPID_PRIVATE_KEY configurados, o envio é
apenas logado (no-op) — não bloqueia a mudança de status. Para ativar,
gere o par de chaves com `backend/scripts/gerar_chaves_vapid.py` e defina as
duas variáveis de ambiente.
"""

import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from app.config import settings
from app.models.enums import TipoRastreioPush
from app.models.push_inscricao import PushInscricao
from app.schemas.push import InscricaoPushRequest

logger = logging.getLogger("gotur.push")


def push_configurado() -> bool:
    return bool(settings.vapid_public_key and settings.vapid_private_key)


def inscrever(db: Session, *, tenant_id: int, tipo: TipoRastreioPush, objeto_id: int, dados: InscricaoPushRequest) -> PushInscricao:
    """Idempotente: se esse mesmo navegador (endpoint) já está inscrito
    nesse código de rastreio, não duplica."""
    existente = (
        db.query(PushInscricao)
        .filter(
            PushInscricao.tenant_id == tenant_id,
            PushInscricao.tipo == tipo,
            PushInscricao.objeto_id == objeto_id,
            PushInscricao.endpoint == dados.endpoint,
        )
        .first()
    )
    if existente:
        return existente

    inscricao = PushInscricao(
        tenant_id=tenant_id,
        tipo=tipo,
        objeto_id=objeto_id,
        endpoint=dados.endpoint,
        p256dh=dados.keys.p256dh,
        auth=dados.keys.auth,
    )
    db.add(inscricao)
    db.commit()
    db.refresh(inscricao)
    return inscricao


def notificar_inscritos(db: Session, *, tipo: TipoRastreioPush, objeto_id: int, titulo: str, corpo: str, url: str) -> None:
    inscricoes = db.query(PushInscricao).filter(PushInscricao.tipo == tipo, PushInscricao.objeto_id == objeto_id).all()
    for inscricao in inscricoes:
        valida = enviar_push(inscricao, titulo=titulo, corpo=corpo, url=url)
        if not valida:
            db.delete(inscricao)
    if inscricoes:
        db.commit()


def enviar_push(inscricao: PushInscricao, *, titulo: str, corpo: str, url: str) -> bool:
    """Retorna False quando a inscrição não é mais válida (o navegador a
    cancelou) — o chamador deve apagar o registro nesse caso."""
    payload = json.dumps({"title": titulo, "body": corpo, "url": url})

    if not push_configurado():
        logger.info("[Push não enviado - VAPID não configurado] %s: %s", titulo, corpo)
        return True

    try:
        webpush(
            subscription_info={
                "endpoint": inscricao.endpoint,
                "keys": {"p256dh": inscricao.p256dh, "auth": inscricao.auth},
            },
            data=payload,
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": f"mailto:{settings.vapid_claims_email}"},
        )
        return True
    except WebPushException as erro:
        status_code = erro.response.status_code if erro.response is not None else None
        if status_code in (404, 410):
            # Inscrição expirada ou cancelada pelo usuário — não é uma
            # falha de envio, é sinal pra parar de tentar esse destino.
            return False
        logger.exception("Falha ao enviar push notification")
        return True
