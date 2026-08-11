import enum


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN_EMPRESA = "admin_empresa"
    FUNCIONARIO = "funcionario"
    CLIENTE = "cliente"
    PARCEIRO = "parceiro"


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


class StatusFrete(str, enum.Enum):
    SOLICITADO = "solicitado"
    CONFIRMADO = "confirmado"
    EM_TRANSITO = "em_transito"
    ENTREGUE = "entregue"
    CANCELADO = "cancelado"


class TipoCupom(str, enum.Enum):
    PERCENTUAL = "percentual"
    FIXO = "fixo"


class TipoRastreioPush(str, enum.Enum):
    """A qual tipo de registro uma inscrição de push notification está
    vinculada (ver app.models.push_inscricao.PushInscricao)."""

    FRETAMENTO = "fretamento"
    FRETE = "frete"


class TipoDocumento(str, enum.Enum):
    CPF = "cpf"
    RG = "rg"
    CNH = "cnh"
    PASSAPORTE = "passaporte"
    OUTRO = "outro"


class CategoriaPassageiro(str, enum.Enum):
    """Categorias que a legislação brasileira trata de forma diferente na
    venda de passagem rodoviária (vaga gratuita/desconto pra idoso, PCD e
    criança de colo — Estatuto do Idoso e regras da ANTT). Guardar aqui não
    aplica desconto sozinho; é o dado bruto pra empresa comprovar/aplicar
    a regra manualmente por enquanto."""

    COMUM = "comum"
    IDOSO = "idoso"
    PCD = "pcd"
    CRIANCA_COLO = "crianca_colo"


class TipoDocumentoOnibus(str, enum.Enum):
    """Tipo de item com data de vencimento controlado por ônibus (ver
    app.models.documento_onibus.DocumentoOnibus) — cobre tanto documentos
    (CRLV, seguro) quanto manutenção preventiva por data."""

    CRLV = "crlv"
    SEGURO = "seguro"
    REVISAO = "revisao"
    OUTRO = "outro"


class StatusRepasse(str, enum.Enum):
    """Situação de um repasse de comissão gerado pra um parceiro (ver
    app.models.repasse_parceiro.RepasseParceiro) — o pagamento em si
    acontece fora do sistema (Pix, transferência); aqui só se registra o
    valor apurado e se já foi marcado como pago."""

    PENDENTE = "pendente"
    PAGO = "pago"


class StatusPedidoPagamento(str, enum.Enum):
    """Status de uma cobrança Pix pendente de confirmação (compra do
    cliente que ainda não caiu na conta). Cartão, dinheiro e outros meios
    são aprovados na hora e nunca passam por aqui."""

    PENDENTE = "pendente"
    CONFIRMADO = "confirmado"
    EXPIRADO = "expirado"
    CANCELADO = "cancelado"
