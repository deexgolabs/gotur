"""Notificação por WhatsApp via Evolution API (self-hosted).

Sem GOTUR_EVOLUTION_API_URL configurado, o envio é apenas registrado no
log — não bloqueia a venda nem levanta erro. Para ativar de verdade, suba
uma instância da Evolution API (https://github.com/EvolutionAPI/evolution-api),
conecte um número e configure:

    GOTUR_EVOLUTION_API_URL=https://sua-evolution.exemplo.com
    GOTUR_EVOLUTION_API_KEY=xxxx
    GOTUR_EVOLUTION_INSTANCE=nome-da-instancia

O envio usa o endpoint `POST {url}/message/sendText/{instance}` da
Evolution API v2, autenticado pelo header `apikey`.
"""

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime

from app.config import settings

logger = logging.getLogger("gotur.whatsapp")


def _normalizar_numero(telefone: str) -> str:
    """Evolution API espera só dígitos, com DDI — sem +, espaço, traço ou
    parênteses. Assume Brasil (55) quando o número não vier com DDI."""
    digitos = "".join(c for c in telefone if c.isdigit())
    if len(digitos) <= 11:
        digitos = f"55{digitos}"
    return digitos


def _enviar(telefone: str | None, mensagem: str) -> None:
    if not telefone:
        return

    if not settings.evolution_api_url or not settings.evolution_instance:
        logger.info("[WhatsApp não enviado - Evolution API não configurada] Para: %s\n%s", telefone, mensagem)
        return

    numero = _normalizar_numero(telefone)
    url = f"{settings.evolution_api_url.rstrip('/')}/message/sendText/{settings.evolution_instance}"
    corpo = json.dumps({"number": numero, "text": mensagem}).encode("utf-8")
    requisicao = urllib.request.Request(
        url,
        data=corpo,
        headers={
            "Content-Type": "application/json",
            "apikey": settings.evolution_api_key or "",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=10):
            pass
    except (urllib.error.URLError, urllib.error.HTTPError):
        logger.exception("Falha ao enviar WhatsApp (Evolution API) para %s", telefone)


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
    mensagem = (
        f"Olá, {cliente_nome}! Sua passagem GoTur está confirmada.\n"
        f"Localizador: {localizador}\n"
        f"{origem} -> {destino} em {data_hora_partida.strftime('%d/%m/%Y %H:%M')}\n"
        f"Poltrona: {numero_poltrona}\n"
        f"Boa viagem!"
    )
    _enviar(telefone, mensagem)


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
    rotulo = ROTULOS_STATUS_FRETAMENTO.get(novo_status, novo_status)
    mensagem = (
        f"Olá, {cliente_nome}! O status do seu fretamento ({origem} -> {destino}) mudou para: {rotulo}.\n"
        f"Acompanhe por aqui: {link_acompanhar}"
    )
    _enviar(telefone, mensagem)


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
    rotulo = ROTULOS_STATUS_FRETE.get(novo_status, novo_status)
    mensagem = (
        f"Olá, {nome}! O status da sua encomenda ({origem} -> {destino}) mudou para: {rotulo}.\n"
        f"Acompanhe por aqui: {link_acompanhar}"
    )
    _enviar(telefone, mensagem)


def enviar_fatura_gerada_whatsapp(
    *,
    telefone: str | None,
    empresa_nome: str,
    valor: float,
    vencimento,
    link_pagamento: str,
) -> None:
    mensagem = (
        f"Olá, {empresa_nome}! A fatura da sua assinatura do GoTur foi gerada: "
        f"R$ {valor:.2f}, vencimento {vencimento.strftime('%d/%m/%Y')}.\n"
        f"Pague por aqui: {link_pagamento}"
    )
    _enviar(telefone, mensagem)
