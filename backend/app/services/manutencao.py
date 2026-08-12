"""Alerta proativo de vencimento de documento da frota — fecha o ciclo que
a tela de Manutenção começa: hoje o selo "vencendo/vencido" só aparece se
alguém abrir a tela de um ônibus específico; isso avisa a empresa sozinho,
por e-mail e WhatsApp, agrupando tudo que está perto de vencer num só
envio (ver scripts/verificar_vencimentos.py, pensado pra rodar 1x por dia)."""

from datetime import date, timedelta

from sqlalchemy.orm import Session, joinedload

from app.models.documento_onibus import DocumentoOnibus
from app.models.empresa import Empresa
from app.models.enums import TipoDocumentoOnibus
from app.services.notificacoes import enviar_alerta_documentos_vencendo
from app.services.whatsapp_service import enviar_alerta_documentos_vencendo_whatsapp

ROTULOS_TIPO_DOCUMENTO = {
    TipoDocumentoOnibus.CRLV: "CRLV",
    TipoDocumentoOnibus.SEGURO: "Seguro",
    TipoDocumentoOnibus.REVISAO: "Revisão preventiva",
    TipoDocumentoOnibus.OUTRO: "Outro",
}


def verificar_documentos_vencendo(db: Session, dias_alerta: int = 15) -> int:
    """Notifica cada empresa com documento vencendo nos próximos
    `dias_alerta` dias (incluindo hoje). Devolve quantas empresas foram
    notificadas."""
    hoje = date.today()
    limite = hoje + timedelta(days=dias_alerta)

    documentos = (
        db.query(DocumentoOnibus)
        .options(joinedload(DocumentoOnibus.onibus))
        .filter(DocumentoOnibus.data_vencimento >= hoje, DocumentoOnibus.data_vencimento <= limite)
        .order_by(DocumentoOnibus.data_vencimento)
        .all()
    )

    por_empresa: dict[int, list[DocumentoOnibus]] = {}
    for documento in documentos:
        por_empresa.setdefault(documento.tenant_id, []).append(documento)

    for tenant_id, docs in por_empresa.items():
        empresa = db.get(Empresa, tenant_id)
        if not empresa:
            continue
        itens = [
            (
                doc.onibus.identificacao if doc.onibus else "?",
                ROTULOS_TIPO_DOCUMENTO.get(doc.tipo, doc.tipo.value),
                doc.data_vencimento,
            )
            for doc in docs
        ]
        enviar_alerta_documentos_vencendo(destinatario_email=empresa.email_contato, empresa_nome=empresa.nome, itens=itens)
        enviar_alerta_documentos_vencendo_whatsapp(telefone=empresa.telefone_contato, empresa_nome=empresa.nome, itens=itens)

    return len(por_empresa)
