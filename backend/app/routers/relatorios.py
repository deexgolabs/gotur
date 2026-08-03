from datetime import date, datetime, time

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles
from app.database import get_db
from app.models.enums import StatusPassagem, StatusPoltrona, UserRole
from app.models.pagamento import Pagamento
from app.models.passagem import Passagem
from app.models.poltrona_viagem import PoltronaViagem
from app.models.usuario import Usuario
from app.models.viagem import Viagem
from app.schemas.relatorio import OcupacaoViagemOut, VendasPorFuncionarioOut, VendasResumoOut

router = APIRouter(prefix="/relatorios", tags=["relatorios"])


@router.get("/ocupacao", response_model=list[OcupacaoViagemOut])
def relatorio_ocupacao(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    viagens = (
        db.query(Viagem)
        .options(joinedload(Viagem.rota))
        .filter(Viagem.tenant_id == usuario_atual.tenant_id, Viagem.ativo.is_(True))
        .order_by(Viagem.data_hora_partida.desc())
        .all()
    )

    resultado = []
    for v in viagens:
        total = db.query(func.count(PoltronaViagem.id)).filter(PoltronaViagem.viagem_id == v.id).scalar() or 0
        vendidas = (
            db.query(func.count(PoltronaViagem.id))
            .filter(PoltronaViagem.viagem_id == v.id, PoltronaViagem.status == StatusPoltrona.VENDIDA)
            .scalar()
            or 0
        )
        resultado.append(
            OcupacaoViagemOut(
                viagem_id=v.id,
                origem=v.rota.origem,
                destino=v.rota.destino,
                data_hora_partida=v.data_hora_partida,
                total_poltronas=total,
                poltronas_vendidas=vendidas,
                percentual_ocupacao=round((vendidas / total * 100) if total else 0, 1),
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
