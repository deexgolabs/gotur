import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import StatusFatura, StatusPedidoInterline, StatusPedidoPagamento
from app.models.fatura_empresa import FaturaEmpresa
from app.models.interline import ConexaoInterline, PedidoInterline
from app.models.pedido_pagamento import PedidoPagamento
from app.routers.faturas import _marcar_fatura_paga
from app.routers.interline import _criar_passagens_do_pedido_interline
from app.routers.pedidos_pagamento import confirmar_pedido_pagamento
from app.services.pagamento_provider import MercadoPagoProvider, _chave_ativa, obter_configuracao_plataforma

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger("gotur.webhooks")


@router.post("/mercadopago")
async def webhook_mercadopago(request: Request, db: Session = Depends(get_db)):
    """Sem autenticação — é o próprio Mercado Pago que chama essa URL
    quando um pagamento muda de status (a `notification_url` enviada em
    `MercadoPagoProvider._cobrar_pix`/`_cobrar_cartao`). Nunca confia no
    corpo da notificação por si só (qualquer um poderia forjar um POST
    pra essa URL): sempre revalida server-a-server via `consultar_status()`
    usando a credencial certa antes de confirmar qualquer coisa.

    Aceita tanto o formato v2 (JSON `{"type": "payment", "data": {"id": ...}}`)
    quanto o formato de query string mais antigo (`?type=payment&data.id=...`
    ou `?topic=payment&id=...`) que o Mercado Pago ainda manda em alguns
    fluxos. Sempre responde 200 rapidinho — é o que o Mercado Pago espera,
    mesmo quando a notificação não corresponde a nada conhecido aqui."""
    try:
        corpo = await request.json()
    except Exception:
        corpo = {}

    dados = corpo.get("data") if isinstance(corpo.get("data"), dict) else {}
    payment_id = dados.get("id") or request.query_params.get("data.id") or request.query_params.get("id")
    tipo = corpo.get("type") or request.query_params.get("type") or request.query_params.get("topic")

    if not payment_id or (tipo and tipo != "payment"):
        return {"status": "ignorado"}

    payment_id = str(payment_id)

    pedido = (
        db.query(PedidoPagamento)
        .filter(PedidoPagamento.gateway_ref == payment_id, PedidoPagamento.status == StatusPedidoPagamento.PENDENTE)
        .first()
    )
    if pedido:
        empresa = db.get(Empresa, pedido.tenant_id)
        chave = _chave_ativa(empresa, None)
        if not chave:
            logger.warning("Webhook Mercado Pago: pedido %s pendente sem nenhuma credencial ativa pra revalidar", pedido.id)
            return {"status": "sem_credencial"}

        status_mp = MercadoPagoProvider(chave).consultar_status(payment_id)
        if status_mp == "approved":
            try:
                confirmar_pedido_pagamento(db, pedido, gateway_ref=payment_id)
            except HTTPException:
                logger.exception("Webhook Mercado Pago: falha ao confirmar pedido %s (payment_id=%s)", pedido.id, payment_id)
        return {"status": "processado"}

    pedido_interline = (
        db.query(PedidoInterline)
        .filter(PedidoInterline.gateway_ref == payment_id, PedidoInterline.status == StatusPedidoInterline.PENDENTE_PAGAMENTO)
        .first()
    )
    if pedido_interline:
        conexao = db.get(ConexaoInterline, pedido_interline.conexao_id)
        empresa_vendedora = db.get(Empresa, conexao.empresa_a_id) if conexao else None
        chave = _chave_ativa(empresa_vendedora, None)
        if not chave:
            logger.warning(
                "Webhook Mercado Pago: pedido interline %s pendente sem nenhuma credencial ativa pra revalidar", pedido_interline.id
            )
            return {"status": "sem_credencial"}

        status_mp = MercadoPagoProvider(chave).consultar_status(payment_id)
        if status_mp == "approved":
            try:
                _criar_passagens_do_pedido_interline(db, pedido_interline, gateway_ref_perna_a=payment_id)
            except HTTPException:
                logger.exception(
                    "Webhook Mercado Pago: falha ao confirmar pedido interline %s (payment_id=%s)", pedido_interline.id, payment_id
                )
        return {"status": "processado"}

    fatura = (
        db.query(FaturaEmpresa)
        .filter(FaturaEmpresa.gateway_ref == payment_id, FaturaEmpresa.status == StatusFatura.PENDENTE)
        .first()
    )
    if fatura:
        plataforma = obter_configuracao_plataforma(db)
        chave = _chave_ativa(None, plataforma)
        if not chave:
            logger.warning("Webhook Mercado Pago: fatura %s pendente sem nenhuma credencial ativa pra revalidar", fatura.id)
            return {"status": "sem_credencial"}

        status_mp = MercadoPagoProvider(chave).consultar_status(payment_id)
        if status_mp == "approved":
            _marcar_fatura_paga(db, fatura, None, payment_id)
            db.commit()
        return {"status": "processado"}

    logger.info("Webhook Mercado Pago: nenhum pedido/fatura pendente encontrado pra payment_id=%s", payment_id)
    return {"status": "nao_encontrado"}
