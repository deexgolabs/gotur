"""Notificação por WhatsApp (Fase 5).

Sem GOTUR_WHATSAPP_API_URL configurado, o envio é apenas registrado no log
— não bloqueia a venda nem levanta erro. Para ativar de verdade, configure
GOTUR_WHATSAPP_API_URL e GOTUR_WHATSAPP_API_TOKEN com as credenciais de um
provedor real (ex: Z-API, Twilio, Meta Cloud API for WhatsApp).

O formato exato do payload varia por provedor — ajuste `_montar_payload`
para o provedor escolhido antes de ativar em produção.
"""

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime

from app.config import settings

logger = logging.getLogger("gotur.whatsapp")


def _montar_mensagem(cliente_nome: str, localizador: str, origem: str, destino: str, data_hora_partida: datetime, numero_poltrona: str) -> str:
    return (
        f"Olá, {cliente_nome}! Sua passagem GoTur está confirmada.\n"
        f"Localizador: {localizador}\n"
        f"{origem} -> {destino} em {data_hora_partida.strftime('%d/%m/%Y %H:%M')}\n"
        f"Poltrona: {numero_poltrona}\n"
        f"Boa viagem!"
    )


def _montar_payload(numero: str, mensagem: str) -> bytes:
    return json.dumps({"phone": numero, "message": mensagem}).encode("utf-8")


def enviar_confirmacao_compra_whatsapp(
    *,
    telefone: str | None,
    cliente_nome: str,
    localizador: str,
    origem: str,
    destino: str,
    data_hora_partida: datetime,
    numero_poltrona: str,
) -> None:
    if not telefone:
        return

    mensagem = _montar_mensagem(cliente_nome, localizador, origem, destino, data_hora_partida, numero_poltrona)

    if not settings.whatsapp_api_url:
        logger.info("[WhatsApp não enviado - provedor não configurado] Para: %s\n%s", telefone, mensagem)
        return

    requisicao = urllib.request.Request(
        settings.whatsapp_api_url,
        data=_montar_payload(telefone, mensagem),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.whatsapp_api_token}" if settings.whatsapp_api_token else "",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=10):
            pass
    except (urllib.error.URLError, urllib.error.HTTPError):
        logger.exception("Falha ao enviar WhatsApp de confirmação para %s", telefone)


ROTULOS_STATUS_FRETAMENTO = {
    "orcamento": "Orçamento",
    "confirmado": "Confirmado",
    "em_andamento": "Em andamento",
    "concluido": "Concluído",
    "cancelado": "Cancelado",
}


def enviar_atualizacao_status_fretamento_whatsapp(
    *,
    telefone: str | None,
    cliente_nome: str,
    origem: str,
    destino: str,
    novo_status: str,
    link_acompanhar: str,
) -> None:
    if not telefone:
        return

    rotulo = ROTULOS_STATUS_FRETAMENTO.get(novo_status, novo_status)
    mensagem = (
        f"Olá, {cliente_nome}! O status do seu fretamento ({origem} -> {destino}) mudou para: {rotulo}.\n"
        f"Acompanhe por aqui: {link_acompanhar}"
    )

    if not settings.whatsapp_api_url:
        logger.info("[WhatsApp não enviado - provedor não configurado] Para: %s\n%s", telefone, mensagem)
        return

    requisicao = urllib.request.Request(
        settings.whatsapp_api_url,
        data=_montar_payload(telefone, mensagem),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.whatsapp_api_token}" if settings.whatsapp_api_token else "",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=10):
            pass
    except (urllib.error.URLError, urllib.error.HTTPError):
        logger.exception("Falha ao enviar WhatsApp de atualização de fretamento para %s", telefone)


ROTULOS_STATUS_FRETE = {
    "solicitado": "Solicitado",
    "confirmado": "Confirmado",
    "em_transito": "Em trânsito",
    "entregue": "Entregue",
    "cancelado": "Cancelado",
}


def enviar_atualizacao_status_frete_whatsapp(
    *,
    telefone: str | None,
    nome: str,
    origem: str,
    destino: str,
    novo_status: str,
    link_acompanhar: str,
) -> None:
    if not telefone:
        return

    rotulo = ROTULOS_STATUS_FRETE.get(novo_status, novo_status)
    mensagem = (
        f"Olá, {nome}! O status da sua encomenda ({origem} -> {destino}) mudou para: {rotulo}.\n"
        f"Acompanhe por aqui: {link_acompanhar}"
    )

    if not settings.whatsapp_api_url:
        logger.info("[WhatsApp não enviado - provedor não configurado] Para: %s\n%s", telefone, mensagem)
        return

    requisicao = urllib.request.Request(
        settings.whatsapp_api_url,
        data=_montar_payload(telefone, mensagem),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.whatsapp_api_token}" if settings.whatsapp_api_token else "",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=10):
            pass
    except (urllib.error.URLError, urllib.error.HTTPError):
        logger.exception("Falha ao enviar WhatsApp de atualização de frete para %s", telefone)
