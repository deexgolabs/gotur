from pydantic import BaseModel, ConfigDict


class PlanoCreate(BaseModel):
    nome: str
    descricao: str | None = None
    preco_mensal: float
    max_onibus: int | None = None
    max_funcionarios: int | None = None
    max_viagens_mes: int | None = None
    max_locais: int | None = None
    max_sessoes_mes: int | None = None
    max_turmas: int | None = None
    max_matriculas_ativas: int | None = None
    modulo_fretamento: bool = True
    modulo_passagens: bool = True
    modulo_frete: bool = True
    modulo_eventos: bool = True
    modulo_academia: bool = True
    modulo_frota: bool = True
    modulo_motorista: bool = True
    modulo_dre: bool = True
    modulo_white_label: bool = True
    modulo_nfse: bool = True


class PlanoUpdate(BaseModel):
    nome: str | None = None
    descricao: str | None = None
    preco_mensal: float | None = None
    max_onibus: int | None = None
    max_funcionarios: int | None = None
    max_viagens_mes: int | None = None
    max_locais: int | None = None
    max_sessoes_mes: int | None = None
    max_turmas: int | None = None
    max_matriculas_ativas: int | None = None
    modulo_fretamento: bool | None = None
    modulo_passagens: bool | None = None
    modulo_frete: bool | None = None
    modulo_eventos: bool | None = None
    modulo_academia: bool | None = None
    modulo_frota: bool | None = None
    modulo_motorista: bool | None = None
    modulo_dre: bool | None = None
    modulo_white_label: bool | None = None
    modulo_nfse: bool | None = None


class PlanoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    descricao: str | None
    preco_mensal: float
    max_onibus: int | None
    max_funcionarios: int | None
    max_viagens_mes: int | None
    max_locais: int | None = None
    max_sessoes_mes: int | None = None
    max_turmas: int | None = None
    max_matriculas_ativas: int | None = None
    ativo: bool
    modulo_fretamento: bool = True
    modulo_passagens: bool = True
    modulo_frete: bool = True
    modulo_eventos: bool = True
    modulo_academia: bool = True
    modulo_frota: bool = True
    modulo_motorista: bool = True
    modulo_dre: bool = True
    modulo_white_label: bool = True
    modulo_nfse: bool = True
