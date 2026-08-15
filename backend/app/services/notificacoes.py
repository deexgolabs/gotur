"""Notificação por e-mail (Fase 5).

Sem GOTUR_SMTP_HOST configurado, o envio é apenas registrado no log — não
bloqueia a venda nem levanta erro. Para ativar de verdade, configure as
variáveis de ambiente GOTUR_SMTP_HOST/PORT/USER/PASSWORD/FROM com as
credenciais de um provedor SMTP real (ex: SendGrid, Amazon SES, Gmail).
"""

import logging
import smtplib
from datetime import date, datetime
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger("gotur.notificacoes")


def _montar_corpo(cliente_nome: str, localizador: str, origem: str, destino: str, data_hora_partida: datetime, numero_poltrona: str, preco: float) -> str:
    return (
        f"Olá, {cliente_nome}!\n\n"
        f"Sua passagem foi confirmada.\n\n"
        f"Localizador: {localizador}\n"
        f"Trecho: {origem} -> {destino}\n"
        f"Partida: {data_hora_partida.strftime('%d/%m/%Y %H:%M')}\n"
        f"Poltrona: {numero_poltrona}\n"
        f"Valor: R$ {preco:.2f}\n\n"
        f"Apresente o código acima (ou o QR Code disponível em 'Minhas passagens') no embarque.\n\n"
        f"Boa viagem!\nKivo"
    )


def enviar_confirmacao_compra(
    *,
    destinatario_email: str | None,
    cliente_nome: str,
    localizador: str,
    origem: str,
    destino: str,
    data_hora_partida: datetime,
    numero_poltrona: str,
    preco: float,
) -> None:
    if not destinatario_email:
        return

    corpo = _montar_corpo(cliente_nome, localizador, origem, destino, data_hora_partida, numero_poltrona, preco)

    if not settings.smtp_host:
        logger.info("[e-mail não enviado - SMTP não configurado] Para: %s\n%s", destinatario_email, corpo)
        return

    mensagem = EmailMessage()
    mensagem["Subject"] = f"Kivo - Passagem confirmada ({localizador})"
    mensagem["From"] = settings.smtp_remetente
    mensagem["To"] = destinatario_email
    mensagem.set_content(corpo)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(mensagem)
    except Exception:
        logger.exception("Falha ao enviar e-mail de confirmação para %s", destinatario_email)


ROTULOS_STATUS_FRETAMENTO = {
    "orcamento": "Orçamento",
    "confirmado": "Confirmado",
    "em_andamento": "Em andamento",
    "concluido": "Concluído",
    "cancelado": "Cancelado",
}


def enviar_atualizacao_status_fretamento(
    *,
    destinatario_email: str | None,
    cliente_nome: str,
    origem: str,
    destino: str,
    novo_status: str,
    link_acompanhar: str,
) -> None:
    if not destinatario_email:
        return

    rotulo = ROTULOS_STATUS_FRETAMENTO.get(novo_status, novo_status)
    corpo = (
        f"Olá, {cliente_nome}!\n\n"
        f"O status do seu fretamento ({origem} -> {destino}) mudou para: {rotulo}.\n\n"
        f"Acompanhe os detalhes e o trajeto por aqui: {link_acompanhar}\n\n"
        f"Kivo"
    )

    if not settings.smtp_host:
        logger.info("[e-mail não enviado - SMTP não configurado] Para: %s\n%s", destinatario_email, corpo)
        return

    mensagem = EmailMessage()
    mensagem["Subject"] = f"Kivo - Fretamento atualizado: {rotulo}"
    mensagem["From"] = settings.smtp_remetente
    mensagem["To"] = destinatario_email
    mensagem.set_content(corpo)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(mensagem)
    except Exception:
        logger.exception("Falha ao enviar e-mail de atualização de fretamento para %s", destinatario_email)


ROTULOS_STATUS_FRETE = {
    "solicitado": "Solicitado",
    "confirmado": "Confirmado",
    "em_transito": "Em trânsito",
    "entregue": "Entregue",
    "cancelado": "Cancelado",
}


def enviar_fatura_gerada(
    *,
    destinatario_email: str | None,
    empresa_nome: str,
    valor: float,
    vencimento,
    link_pagamento: str,
) -> None:
    if not destinatario_email:
        return

    corpo = (
        f"Olá, {empresa_nome}!\n\n"
        f"A fatura da sua assinatura do Kivo foi gerada.\n\n"
        f"Valor: R$ {valor:.2f}\n"
        f"Vencimento: {vencimento.strftime('%d/%m/%Y')}\n\n"
        f"Pague por aqui pra manter sua conta ativa: {link_pagamento}\n\n"
        f"Kivo"
    )

    if not settings.smtp_host:
        logger.info("[e-mail não enviado - SMTP não configurado] Para: %s\n%s", destinatario_email, corpo)
        return

    mensagem = EmailMessage()
    mensagem["Subject"] = f"Kivo - Fatura gerada (vence {vencimento.strftime('%d/%m/%Y')})"
    mensagem["From"] = settings.smtp_remetente
    mensagem["To"] = destinatario_email
    mensagem.set_content(corpo)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(mensagem)
    except Exception:
        logger.exception("Falha ao enviar e-mail de fatura gerada para %s", destinatario_email)


def enviar_atualizacao_status_frete(
    *,
    destinatario_email: str | None,
    nome: str,
    origem: str,
    destino: str,
    novo_status: str,
    link_acompanhar: str,
) -> None:
    if not destinatario_email:
        return

    rotulo = ROTULOS_STATUS_FRETE.get(novo_status, novo_status)
    corpo = (
        f"Olá, {nome}!\n\n"
        f"O status da sua encomenda ({origem} -> {destino}) mudou para: {rotulo}.\n\n"
        f"Acompanhe o trajeto por aqui: {link_acompanhar}\n\n"
        f"Kivo"
    )

    if not settings.smtp_host:
        logger.info("[e-mail não enviado - SMTP não configurado] Para: %s\n%s", destinatario_email, corpo)
        return

    mensagem = EmailMessage()
    mensagem["Subject"] = f"Kivo - Encomenda atualizada: {rotulo}"
    mensagem["From"] = settings.smtp_remetente
    mensagem["To"] = destinatario_email
    mensagem.set_content(corpo)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(mensagem)
    except Exception:
        logger.exception("Falha ao enviar e-mail de atualização de frete para %s", destinatario_email)


def enviar_alerta_documentos_vencendo(
    *,
    destinatario_email: str | None,
    empresa_nome: str,
    itens: list[tuple[str, str, date]],
) -> None:
    """`itens`: lista de (identificação do ônibus, tipo do documento, data de
    vencimento) — um e-mail só, agrupando tudo que está vencendo, em vez de
    um por documento."""
    if not destinatario_email:
        return

    linhas = "\n".join(f"- {onibus}: {tipo}, vence em {venc.strftime('%d/%m/%Y')}" for onibus, tipo, venc in itens)
    corpo = (
        f"Olá, {empresa_nome}!\n\n"
        f"Os seguintes documentos da sua frota estão perto de vencer:\n\n"
        f"{linhas}\n\n"
        f"Acesse Ônibus > Manutenção no painel do Kivo pra renovar.\n\n"
        f"Kivo"
    )

    if not settings.smtp_host:
        logger.info("[e-mail não enviado - SMTP não configurado] Para: %s\n%s", destinatario_email, corpo)
        return

    mensagem = EmailMessage()
    mensagem["Subject"] = f"Kivo - {len(itens)} documento(s) da frota vencendo"
    mensagem["From"] = settings.smtp_remetente
    mensagem["To"] = destinatario_email
    mensagem.set_content(corpo)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(mensagem)
    except Exception:
        logger.exception("Falha ao enviar e-mail de alerta de documentos vencendo para %s", destinatario_email)
