import enum


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN_EMPRESA = "admin_empresa"
    FUNCIONARIO = "funcionario"
    CLIENTE = "cliente"


class TipoOnibus(str, enum.Enum):
    CONVENCIONAL = "convencional"
    EXECUTIVO = "executivo"
    LEITO = "leito"


class StatusPoltrona(str, enum.Enum):
    LIVRE = "livre"
    HOLD = "hold"
    BLOQUEADA = "bloqueada"
    VENDIDA = "vendida"


class TipoOcupacao(str, enum.Enum):
    """Tipo de um registro no "livro-razão" de ocupação de poltrona por
    trecho (app.models.ocupacao_poltrona.OcupacaoPoltrona)."""

    HOLD = "hold"
    BLOQUEIO = "bloqueio"
    VENDA = "venda"


class StatusPassagem(str, enum.Enum):
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"


class FormaPagamento(str, enum.Enum):
    DINHEIRO = "dinheiro"
    CARTAO = "cartao"
    PIX = "pix"
    OUTRO = "outro"


class StatusAssinatura(str, enum.Enum):
    """Situação da assinatura da empresa na plataforma (não confundir com
    `Empresa.ativo`, que é um desligamento manual pelo super admin)."""

    TRIAL = "trial"
    ATIVA = "ativa"
    INADIMPLENTE = "inadimplente"
    SUSPENSA = "suspensa"
    CANCELADA = "cancelada"


class StatusFatura(str, enum.Enum):
    PENDENTE = "pendente"
    PAGA = "paga"
    FALHOU = "falhou"
    CANCELADA = "cancelada"


class StatusFretamento(str, enum.Enum):
    ORCAMENTO = "orcamento"
    CONFIRMADO = "confirmado"
    EM_ANDAMENTO = "em_andamento"
    CONCLUIDO = "concluido"
    CANCELADO = "cancelado"
