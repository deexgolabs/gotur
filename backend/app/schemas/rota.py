from pydantic import BaseModel, ConfigDict, Field, model_validator


class ParadaCreate(BaseModel):
    nome: str
    peso_proximo: float | None = 1.0


class RotaCreate(BaseModel):
    origem: str
    destino: str
    paradas: list[ParadaCreate] = Field(
        default_factory=list,
        description=(
            "Paradas intermediárias em ordem, entre origem e destino (opcional). "
            "Se vazio, a rota tem só origem->destino direto."
        ),
    )

    @model_validator(mode="after")
    def _validar(self) -> "RotaCreate":
        for parada in self.paradas:
            if parada.peso_proximo is not None and parada.peso_proximo <= 0:
                raise ValueError("O peso de cada trecho deve ser maior que zero")
        if self.paradas:
            if len(self.paradas) < 2:
                raise ValueError("Informe ao menos origem e destino em `paradas`, ou deixe a lista vazia")
            if self.paradas[0].nome != self.origem:
                raise ValueError("O primeiro item de `paradas` deve ter o mesmo nome de `origem`")
            if self.paradas[-1].nome != self.destino:
                raise ValueError("O último item de `paradas` deve ter o mesmo nome de `destino`")
        return self


class RotaUpdate(BaseModel):
    origem: str | None = None
    destino: str | None = None


class ParadaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    ordem: int
    peso_proximo: float | None = None


class RotaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    origem: str
    destino: str
    ativo: bool
    paradas: list[ParadaOut] = Field(default_factory=list)
