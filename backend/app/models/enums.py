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


class StatusPassagem(str, enum.Enum):
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"


class FormaPagamento(str, enum.Enum):
    DINHEIRO = "dinheiro"
    CARTAO = "cartao"
    PIX = "pix"
    OUTRO = "outro"
