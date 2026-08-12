from app.models.auditoria import RegistroAuditoria
from app.models.avaliacao import Avaliacao
from app.models.cupom import Cupom
from app.models.documento_onibus import DocumentoOnibus
from app.models.empresa import Empresa
from app.models.fatura_empresa import FaturaEmpresa
from app.models.frete import Frete, PosicaoFrete
from app.models.fretamento import Fretamento, PosicaoFretamento
from app.models.jornada_motorista import JornadaMotorista
from app.models.motorista import Motorista
from app.models.ocupacao_poltrona import OcupacaoPoltrona
from app.models.onibus import Onibus, PoltronaOnibus
from app.models.pagamento import Pagamento
from app.models.parada import Parada
from app.models.passagem import Passagem
from app.models.parceiro import Parceiro
from app.models.pedido_pagamento import PedidoPagamento
from app.models.plano import Plano
from app.models.poltrona_viagem import PoltronaViagem
from app.models.push_inscricao import PushInscricao
from app.models.repasse_parceiro import RepasseParceiro
from app.models.rota import Rota
from app.models.usuario import Usuario
from app.models.viagem import Viagem

__all__ = [
    "RegistroAuditoria",
    "Avaliacao",
    "Cupom",
    "DocumentoOnibus",
    "Empresa",
    "Plano",
    "FaturaEmpresa",
    "Usuario",
    "Onibus",
    "PoltronaOnibus",
    "Rota",
    "Parada",
    "Viagem",
    "PoltronaViagem",
    "OcupacaoPoltrona",
    "Passagem",
    "Pagamento",
    "PedidoPagamento",
    "Fretamento",
    "PosicaoFretamento",
    "Frete",
    "PosicaoFrete",
    "PushInscricao",
    "Parceiro",
    "RepasseParceiro",
    "JornadaMotorista",
    "Motorista",
]
