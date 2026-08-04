from datetime import date, datetime, time

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles
from app.database import get_db
from app.models.enums import StatusPassagem, TipoOcupacao, UserRole
from app.models.ocupacao_poltrona import OcupacaoPoltrona
from app.models.pagamento import Pagamento
from app.models.passagem import Passagem
from app.models.poltrona_viagem import PoltronaViagem
from app.models.usuario import Usuario
from app.models.viagem import Viagem
from app.schemas.relatorio import OcupacaoViagemOut, VendasPorFuncionarioOut, VendasResumoOut
from app.services.trecho import buscar_paradas_da_rota

router = APIRouter(prefix="/relatorios", tags=["relatorios"])


@router.get("/ocupacao", response_model=list[OcupacaoViagemOut])
def relatorio_ocupacao(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """`percentual_ocupacao` é o fator de ocupação médio (load factor):
    considera venda de trechos parciais, não só poltronas inteiras vendidas
    de ponta a ponta."""
    viagens = (
        db.query(Viagem)
        .options(joinedload(Viagem.rota))
        .filter(Viagem.tenant_id == usuario_atual.tenant_id, Viagem.ativo.is_(True))
        .order_by(Viagem.data_hora_partida.desc())
        .all()
    )

    resultado = []
    for v in viagens:
        paradas = buscar_paradas_da_rota(db, v.rota_id)
        peso_total = sum(float(p.peso_proximo) for p in paradas if p.peso_proximo is not None) or 1.0

        poltronas_ids = [
            pid for (pid,) in db.query(PoltronaViagem.id).filter(PoltronaViagem.viagem_id == v.id).all()
        ]
        total = len(poltronas_ids)

        vendas = (
            db.query(OcupacaoPoltrona)
            .filter(OcupacaoPoltrona.poltrona_viagem_id.in_(poltronas_ids), OcupacaoPoltrona.tipo == TipoOcupacao.VENDA)
            .all()
            if poltronas_ids
            else []
        )

        poltronas_com_venda = {venda.poltrona_viagem_id for venda in vendas}
        peso_vendido = sum(venda.parada_destino_ordem - venda.parada_origem_ordem for venda in vendas)
        # aproximação: pondera pela quantidade de "segmentos" cobertos, já
        # que o peso exato por segmento pode variar por trecho.
        fracao_media = (peso_vendido / (total * max(len(paradas) - 1, 1))) if total else 0

        resultado.append(
            OcupacaoViagemOut(
                viagem_id=v.id,
                origem=v.rota.origem,
                destino=v.rota.destino,
                data_hora_partida=v.data_hora_partida,
                total_poltronas=total,
                poltronas_vendidas=len(poltronas_com_venda),
                percentual_ocupacao=round(min(fracao_media, 1.0) * 100, 1),
            )
        )
    return resultado


@router.get("/vendas", response_model=VendasResumoOut)
def relatorio_vendas(
    inicio: date,
    fim: date,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    inicio_dt = datetime.combine(inicio, time.min)
    fim_dt = datetime.combine(fim, time.max)

    passagens = (
        db.query(Passagem)
        .join(Pagamento, Pagamento.passagem_id == Passagem.id)
        .filter(
            Passagem.tenant_id == usuario_atual.tenant_id,
            Passagem.criado_em.between(inicio_dt, fim_dt),
            Passagem.status == StatusPassagem.CONFIRMADA,
        )
        .options(joinedload(Passagem.pagamento))
        .all()
    )

    por_forma: dict[str, float] = {}
    total = 0.0
    for p in passagens:
        valor = float(p.preco)
        total += valor
        forma = p.pagamento.forma_pagamento.value if p.pagamento else "outro"
        por_forma[forma] = por_forma.get(forma, 0.0) + valor

    return VendasResumoOut(
        periodo_inicio=inicio_dt,
        periodo_fim=fim_dt,
        total_passagens=len(passagens),
        total_arrecadado=round(total, 2),
        por_forma_pagamento={k: round(v, 2) for k, v in por_forma.items()},
    )


@router.get("/funcionarios", response_model=list[VendasPorFuncionarioOut])
def relatorio_por_funcionario(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    linhas = (
        db.query(
            Usuario.id,
            Usuario.nome,
            func.count(Passagem.id).label("total_passagens"),
            func.coalesce(func.sum(Passagem.preco), 0).label("total_arrecadado"),
        )
        .join(Passagem, Passagem.vendido_por_usuario_id == Usuario.id)
        .filter(Passagem.tenant_id == usuario_atual.tenant_id, Passagem.status == StatusPassagem.CONFIRMADA)
        .group_by(Usuario.id, Usuario.nome)
        .order_by(func.coalesce(func.sum(Passagem.preco), 0).desc())
        .all()
    )

    return [
        VendasPorFuncionarioOut(
            usuario_id=linha.id,
            nome=linha.nome,
            total_passagens=linha.total_passagens,
            total_arrecadado=round(float(linha.total_arrecadado), 2),
        )
        for linha in linhas
    ]
