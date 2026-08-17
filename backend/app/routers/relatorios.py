from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles
from app.database import get_db
from app.models.academia import FaturaMatricula
from app.models.empresa import Empresa
from app.models.enums import StatusFatura, StatusFrete, StatusFretamento, StatusPassagem, TipoOcupacao, UserRole
from app.models.evento import Ingresso
from app.models.fatura_empresa import FaturaEmpresa
from app.models.frete import Frete
from app.models.fretamento import Fretamento
from app.models.ocupacao_poltrona import OcupacaoPoltrona
from app.models.pagamento import Pagamento
from app.models.parceiro import Parceiro
from app.models.passagem import Passagem
from app.models.poltrona_viagem import PoltronaViagem
from app.models.usuario import Usuario
from app.models.viagem import Viagem
from app.schemas.dre import DreOut
from app.schemas.relatorio import (
    OcupacaoViagemOut,
    VendasNichoResumoOut,
    VendasPorFuncionarioOut,
    VendasPorParceiroOut,
    VendasResumoOut,
)
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


def _exigir_modulo_eventos(empresa: Empresa) -> None:
    if not empresa.eventos_habilitado:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="O módulo de eventos não está habilitado para sua empresa")


def _exigir_modulo_academia(empresa: Empresa) -> None:
    if not empresa.academia_habilitado:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="O módulo de academia não está habilitado para sua empresa")


@router.get("/vendas-eventos", response_model=VendasNichoResumoOut)
def relatorio_vendas_eventos(
    inicio: date,
    fim: date,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """Equivalente de relatorio_vendas pro módulo de eventos."""
    empresa = db.get(Empresa, usuario_atual.tenant_id)
    _exigir_modulo_eventos(empresa)

    inicio_dt = datetime.combine(inicio, time.min)
    fim_dt = datetime.combine(fim, time.max)

    ingressos = (
        db.query(Ingresso)
        .filter(
            Ingresso.tenant_id == usuario_atual.tenant_id,
            Ingresso.criado_em.between(inicio_dt, fim_dt),
            Ingresso.status == StatusPassagem.CONFIRMADA,
        )
        .all()
    )

    por_forma: dict[str, float] = {}
    total = 0.0
    for i in ingressos:
        valor = float(i.preco)
        total += valor
        forma = i.forma_pagamento.value
        por_forma[forma] = por_forma.get(forma, 0.0) + valor

    return VendasNichoResumoOut(
        periodo_inicio=inicio_dt,
        periodo_fim=fim_dt,
        total_itens=len(ingressos),
        total_arrecadado=round(total, 2),
        por_forma_pagamento={k: round(v, 2) for k, v in por_forma.items()},
    )


@router.get("/vendas-academia", response_model=VendasNichoResumoOut)
def relatorio_vendas_academia(
    inicio: date,
    fim: date,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """Equivalente de relatorio_vendas pro módulo de academia — conta
    faturas de mensalidade pagas no período, não matrículas criadas (uma
    matrícula sem fatura paga ainda não é receita de verdade)."""
    empresa = db.get(Empresa, usuario_atual.tenant_id)
    _exigir_modulo_academia(empresa)

    inicio_dt = datetime.combine(inicio, time.min)
    fim_dt = datetime.combine(fim, time.max)

    faturas = (
        db.query(FaturaMatricula)
        .filter(
            FaturaMatricula.tenant_id == usuario_atual.tenant_id,
            FaturaMatricula.status == StatusFatura.PAGA,
            FaturaMatricula.pago_em.between(inicio_dt, fim_dt),
        )
        .all()
    )

    por_forma: dict[str, float] = {}
    total = 0.0
    for f in faturas:
        valor = float(f.valor)
        total += valor
        forma = f.forma_pagamento.value if f.forma_pagamento else "outro"
        por_forma[forma] = por_forma.get(forma, 0.0) + valor

    return VendasNichoResumoOut(
        periodo_inicio=inicio_dt,
        periodo_fim=fim_dt,
        total_itens=len(faturas),
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


@router.get("/parceiros", response_model=list[VendasPorParceiroOut])
def relatorio_por_parceiro(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """Vendas trazidas por cada parceiro (agência/vendedor externo que
    vende passagem ou despacha frete em nome da empresa) — separado da
    venda direta, pra conciliação de comissão e visão de desempenho."""
    parceiros = db.query(Parceiro).filter(Parceiro.tenant_id == usuario_atual.tenant_id).order_by(Parceiro.nome).all()

    resultado = []
    for parceiro in parceiros:
        total_passagens, total_arrecadado_passagens = (
            db.query(func.count(Passagem.id), func.coalesce(func.sum(Passagem.preco), 0))
            .filter(Passagem.parceiro_id == parceiro.id, Passagem.status == StatusPassagem.CONFIRMADA)
            .first()
        )
        total_fretes, total_arrecadado_fretes = (
            db.query(func.count(Frete.id), func.coalesce(func.sum(Frete.valor_total), 0))
            .filter(Frete.parceiro_id == parceiro.id, Frete.status != StatusFrete.CANCELADO)
            .first()
        )
        total_arrecadado_passagens = round(float(total_arrecadado_passagens), 2)
        total_arrecadado_fretes = round(float(total_arrecadado_fretes), 2)
        comissao_pct = float(parceiro.comissao_percentual) if parceiro.comissao_percentual is not None else 0.0

        resultado.append(
            VendasPorParceiroOut(
                parceiro_id=parceiro.id,
                nome=parceiro.nome,
                comissao_percentual=float(parceiro.comissao_percentual) if parceiro.comissao_percentual is not None else None,
                total_passagens=total_passagens,
                total_arrecadado_passagens=total_arrecadado_passagens,
                total_fretes=total_fretes,
                total_arrecadado_fretes=total_arrecadado_fretes,
                comissao_estimada=round((total_arrecadado_passagens + total_arrecadado_fretes) * comissao_pct / 100, 2),
            )
        )

    resultado.sort(key=lambda r: r.total_arrecadado_passagens + r.total_arrecadado_fretes, reverse=True)
    return resultado


@router.get("/dre", response_model=DreOut)
def relatorio_dre(
    inicio: date,
    fim: date,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """DRE simplificado: receita bruta (passagens + fretamento + frete +
    eventos + academia) menos reembolsos e a assinatura do Kivo paga no
    período. Não é uma contabilidade completa (não inclui outras despesas
    da empresa, como combustível ou salário) — é um resumo pra acompanhar
    receita líquida."""
    empresa = db.get(Empresa, usuario_atual.tenant_id)
    if not empresa.dre_habilitado:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="O módulo de DRE não está habilitado para sua empresa")

    inicio_dt = datetime.combine(inicio, time.min)
    fim_dt = datetime.combine(fim, time.max)

    # Não filtra por status CONFIRMADA de propósito: o valor já foi cobrado
    # na hora da venda, então uma passagem cancelada sem reembolso continua
    # sendo receita — é o reembolso (linha separada abaixo) que efetivamente
    # devolve o dinheiro.
    receita_passagens = (
        db.query(func.coalesce(func.sum(Passagem.preco), 0))
        .filter(
            Passagem.tenant_id == usuario_atual.tenant_id,
            Passagem.criado_em.between(inicio_dt, fim_dt),
        )
        .scalar()
    )

    receita_fretamento = (
        db.query(func.coalesce(func.sum(Fretamento.valor_total), 0))
        .filter(
            Fretamento.tenant_id == usuario_atual.tenant_id,
            Fretamento.status != StatusFretamento.CANCELADO,
            Fretamento.criado_em.between(inicio_dt, fim_dt),
        )
        .scalar()
    )

    receita_frete = (
        db.query(func.coalesce(func.sum(Frete.valor_total), 0))
        .filter(
            Frete.tenant_id == usuario_atual.tenant_id,
            Frete.status != StatusFrete.CANCELADO,
            Frete.criado_em.between(inicio_dt, fim_dt),
        )
        .scalar()
    )

    # Ingresso não filtra por status de propósito, mesmo motivo de
    # receita_passagens: o valor já foi cobrado na venda.
    receita_eventos = (
        db.query(func.coalesce(func.sum(Ingresso.preco), 0))
        .filter(
            Ingresso.tenant_id == usuario_atual.tenant_id,
            Ingresso.criado_em.between(inicio_dt, fim_dt),
        )
        .scalar()
    )

    # Academia reconhece receita no pagamento da fatura, não na criação da
    # matrícula — diferente de passagens/eventos, a mensalidade só é
    # receita de verdade quando o aluno efetivamente paga.
    receita_academia = (
        db.query(func.coalesce(func.sum(FaturaMatricula.valor), 0))
        .filter(
            FaturaMatricula.tenant_id == usuario_atual.tenant_id,
            FaturaMatricula.status == StatusFatura.PAGA,
            FaturaMatricula.pago_em.between(inicio_dt, fim_dt),
        )
        .scalar()
    )

    reembolsos_passagens = (
        db.query(func.coalesce(func.sum(Pagamento.valor_reembolsado), 0))
        .join(Passagem, Passagem.id == Pagamento.passagem_id)
        .filter(Passagem.tenant_id == usuario_atual.tenant_id, Pagamento.reembolsado_em.between(inicio_dt, fim_dt))
        .scalar()
    )

    reembolsos_eventos = (
        db.query(func.coalesce(func.sum(Ingresso.valor_reembolsado), 0))
        .filter(Ingresso.tenant_id == usuario_atual.tenant_id, Ingresso.reembolsado_em.between(inicio_dt, fim_dt))
        .scalar()
    )

    reembolsos = float(reembolsos_passagens) + float(reembolsos_eventos)

    despesa_assinatura = (
        db.query(func.coalesce(func.sum(FaturaEmpresa.valor), 0))
        .filter(
            FaturaEmpresa.empresa_id == usuario_atual.tenant_id,
            FaturaEmpresa.status == StatusFatura.PAGA,
            FaturaEmpresa.pago_em.between(inicio_dt, fim_dt),
        )
        .scalar()
    )

    receita_passagens = round(float(receita_passagens), 2)
    receita_fretamento = round(float(receita_fretamento), 2)
    receita_frete = round(float(receita_frete), 2)
    receita_eventos = round(float(receita_eventos), 2)
    receita_academia = round(float(receita_academia), 2)
    reembolsos = round(reembolsos, 2)
    despesa_assinatura = round(float(despesa_assinatura), 2)
    receita_bruta_total = round(receita_passagens + receita_fretamento + receita_frete + receita_eventos + receita_academia, 2)

    return DreOut(
        periodo_inicio=inicio_dt,
        periodo_fim=fim_dt,
        receita_passagens=receita_passagens,
        receita_fretamento=receita_fretamento,
        receita_frete=receita_frete,
        receita_eventos=receita_eventos,
        receita_academia=receita_academia,
        receita_bruta_total=receita_bruta_total,
        reembolsos=reembolsos,
        despesa_assinatura_gotur=despesa_assinatura,
        receita_liquida=round(receita_bruta_total - reembolsos - despesa_assinatura, 2),
    )
