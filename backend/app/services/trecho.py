"""Lógica de preço e ocupação por trecho (venda por trecho completa).

Uma viagem tem uma sequência ordenada de paradas (`Parada.ordem` 0..N). Um
"trecho" comprado é o intervalo [origem_ordem, destino_ordem). O preço de um
trecho é proporcional ao peso dos segmentos que ele cobre em relação ao peso
total da rota, aplicado sobre `Viagem.preco` (preço da viagem inteira).

Disponibilidade de poltrona por trecho é resolvida consultando
`OcupacaoPoltrona`: dois intervalos [a1,b1) e [a2,b2) se sobrepõem se e
somente se a1 < b2 e a2 < b1.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.enums import StatusPoltrona, TipoOcupacao
from app.models.ocupacao_poltrona import OcupacaoPoltrona
from app.models.parada import Parada


def segmentos_sobrepoem(a1: int, b1: int, a2: int, b2: int) -> bool:
    return a1 < b2 and a2 < b1


def liberar_holds_expirados(db: Session, poltrona_viagem_ids: list[int]) -> None:
    if not poltrona_viagem_ids:
        return
    agora = datetime.now(timezone.utc)
    expirados = (
        db.query(OcupacaoPoltrona)
        .filter(
            OcupacaoPoltrona.poltrona_viagem_id.in_(poltrona_viagem_ids),
            OcupacaoPoltrona.tipo == TipoOcupacao.HOLD,
            OcupacaoPoltrona.expira_em < agora,
        )
        .all()
    )
    for ocupacao in expirados:
        db.delete(ocupacao)
    if expirados:
        db.commit()


def buscar_paradas_da_rota(db: Session, rota_id: int) -> list[Parada]:
    return db.query(Parada).filter(Parada.rota_id == rota_id).order_by(Parada.ordem).all()


def resolver_trecho(paradas: list[Parada], origem_id: int | None, destino_id: int | None) -> tuple[Parada | None, Parada | None]:
    """Resolve a parada de origem/destino do trecho pedido a partir dos ids.
    Sem id informado, usa a ponta correspondente da rota (origem = primeira
    parada, destino = última) — mantém compatibilidade com rotas simples."""
    parada_origem = paradas[0] if origem_id is None else next((p for p in paradas if p.id == origem_id), None)
    parada_destino = paradas[-1] if destino_id is None else next((p for p in paradas if p.id == destino_id), None)
    return parada_origem, parada_destino


def calcular_preco_trecho(paradas: list[Parada], origem_ordem: int, destino_ordem: int, preco_viagem: float) -> float:
    peso_total = sum(float(p.peso_proximo) for p in paradas if p.peso_proximo is not None)
    if peso_total <= 0:
        return float(preco_viagem)

    peso_trecho = sum(
        float(p.peso_proximo)
        for p in paradas
        if p.peso_proximo is not None and origem_ordem <= p.ordem < destino_ordem
    )
    return round(float(preco_viagem) * (peso_trecho / peso_total), 2)


def status_da_poltrona_no_trecho(
    ocupacoes: list[OcupacaoPoltrona], origem_ordem: int, destino_ordem: int
) -> tuple[StatusPoltrona, OcupacaoPoltrona | None]:
    """Retorna o status da poltrona para o trecho [origem_ordem,
    destino_ordem) e a ocupação conflitante (se houver)."""
    relevantes = [
        o
        for o in ocupacoes
        if segmentos_sobrepoem(o.parada_origem_ordem, o.parada_destino_ordem, origem_ordem, destino_ordem)
    ]
    if not relevantes:
        return StatusPoltrona.LIVRE, None

    prioridade = {TipoOcupacao.BLOQUEIO: 3, TipoOcupacao.VENDA: 2, TipoOcupacao.HOLD: 1}
    escolhida = max(relevantes, key=lambda o: prioridade[o.tipo])

    mapa_status = {
        TipoOcupacao.BLOQUEIO: StatusPoltrona.BLOQUEADA,
        TipoOcupacao.VENDA: StatusPoltrona.VENDIDA,
        TipoOcupacao.HOLD: StatusPoltrona.HOLD,
    }
    return mapa_status[escolhida.tipo], escolhida
