from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.core.security import hash_senha
from app.database import get_db
from app.models.enums import StatusFrete, StatusPassagem, StatusRepasse, UserRole
from app.models.frete import Frete
from app.models.parceiro import Parceiro
from app.models.passagem import Passagem
from app.models.repasse_parceiro import RepasseParceiro
from app.models.usuario import Usuario
from app.schemas.parceiro import (
    CriarAcessoParceiroRequest,
    ParceiroCreate,
    ParceiroOut,
    ParceiroUpdate,
    RepasseParceiroOut,
    ResumoParceiroOut,
)
from app.schemas.passagem import PassagemOut
from app.schemas.frete import FreteOut
from app.routers.fretes import _para_out as _frete_para_out

router = APIRouter(prefix="/parceiros", tags=["parceiros"])


def _para_out(db: Session, parceiro: Parceiro) -> ParceiroOut:
    tem_acesso = db.query(Usuario).filter(Usuario.parceiro_id == parceiro.id, Usuario.ativo.is_(True)).first() is not None
    return ParceiroOut(
        id=parceiro.id,
        nome=parceiro.nome,
        documento=parceiro.documento,
        contato=parceiro.contato,
        vende_passagem=parceiro.vende_passagem,
        despacha_frete=parceiro.despacha_frete,
        comissao_percentual=float(parceiro.comissao_percentual) if parceiro.comissao_percentual is not None else None,
        ativo=parceiro.ativo,
        criado_em=parceiro.criado_em,
        tem_acesso=tem_acesso,
    )


@router.post("", response_model=ParceiroOut, status_code=status.HTTP_201_CREATED)
def criar_parceiro(
    dados: ParceiroCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    parceiro = Parceiro(
        tenant_id=usuario_atual.tenant_id,
        nome=dados.nome,
        documento=dados.documento,
        contato=dados.contato,
        vende_passagem=dados.vende_passagem,
        despacha_frete=dados.despacha_frete,
        comissao_percentual=dados.comissao_percentual,
    )
    db.add(parceiro)
    db.commit()
    db.refresh(parceiro)
    return _para_out(db, parceiro)


@router.get("", response_model=list[ParceiroOut])
def listar_parceiros(
    apenas_ativos: bool = False,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA, UserRole.FUNCIONARIO)),
):
    """`apenas_ativos=true` é usado pelos formulários de venda/frete/
    fretamento pra popular o seletor de parceiro (sem mostrar os
    desativados)."""
    query = db.query(Parceiro).filter(Parceiro.tenant_id == usuario_atual.tenant_id)
    if apenas_ativos:
        query = query.filter(Parceiro.ativo.is_(True))
    parceiros = query.order_by(Parceiro.nome).all()
    return [_para_out(db, p) for p in parceiros]


def _buscar_parceiro_da_empresa(db: Session, parceiro_id: int, usuario_atual: Usuario) -> Parceiro:
    parceiro = db.get(Parceiro, parceiro_id)
    if not parceiro or parceiro.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parceiro não encontrado")
    return parceiro


@router.patch("/{parceiro_id}", response_model=ParceiroOut)
def editar_parceiro(
    parceiro_id: int,
    dados: ParceiroUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    parceiro = _buscar_parceiro_da_empresa(db, parceiro_id, usuario_atual)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(parceiro, campo, valor)
    db.commit()
    db.refresh(parceiro)
    return _para_out(db, parceiro)


@router.post("/{parceiro_id}/acesso", response_model=ParceiroOut, status_code=status.HTTP_201_CREATED)
def criar_acesso_parceiro(
    parceiro_id: int,
    dados: CriarAcessoParceiroRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """Cria o login desse parceiro — ele passa a entrar no Vion com e-mail
    e senha próprios e só enxerga as vendas marcadas com o parceiro dele
    (ver /parceiros/minha/*)."""
    parceiro = _buscar_parceiro_da_empresa(db, parceiro_id, usuario_atual)
    if db.query(Usuario).filter(Usuario.email == dados.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado")

    usuario = Usuario(
        tenant_id=usuario_atual.tenant_id,
        nome=parceiro.nome,
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
        role=UserRole.PARCEIRO,
        parceiro_id=parceiro.id,
    )
    db.add(usuario)
    db.commit()
    return _para_out(db, parceiro)


def _repasse_para_out(repasse: RepasseParceiro) -> RepasseParceiroOut:
    return RepasseParceiroOut(
        id=repasse.id,
        parceiro_id=repasse.parceiro_id,
        parceiro_nome=repasse.parceiro.nome if repasse.parceiro else None,
        periodo_inicio=repasse.periodo_inicio,
        periodo_fim=repasse.periodo_fim,
        total_passagens=repasse.total_passagens,
        valor_passagens=float(repasse.valor_passagens),
        total_fretes=repasse.total_fretes,
        valor_fretes=float(repasse.valor_fretes),
        comissao_percentual=float(repasse.comissao_percentual),
        valor_comissao=float(repasse.valor_comissao),
        status=repasse.status,
        criado_em=repasse.criado_em,
        pago_em=repasse.pago_em,
    )


@router.post("/{parceiro_id}/repasses", response_model=RepasseParceiroOut, status_code=status.HTTP_201_CREATED)
def gerar_repasse(
    parceiro_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """Apura passagens e fretes do parceiro desde o último repasse gerado
    (ou desde o cadastro dele, no primeiro repasse) e cria um "a pagar"
    pendente. O pagamento em si acontece fora do sistema — ver
    /repasses/{id}/pagar pra só marcar como quitado."""
    parceiro = _buscar_parceiro_da_empresa(db, parceiro_id, usuario_atual)

    ultimo = (
        db.query(RepasseParceiro)
        .filter(RepasseParceiro.parceiro_id == parceiro.id)
        .order_by(RepasseParceiro.periodo_fim.desc())
        .first()
    )
    inicio = ultimo.periodo_fim if ultimo else parceiro.criado_em
    fim = datetime.now(timezone.utc)

    total_passagens, valor_passagens = (
        db.query(func.count(Passagem.id), func.coalesce(func.sum(Passagem.preco), 0))
        .filter(
            Passagem.parceiro_id == parceiro.id,
            Passagem.status == StatusPassagem.CONFIRMADA,
            Passagem.criado_em > inicio,
            Passagem.criado_em <= fim,
        )
        .first()
    )
    total_fretes, valor_fretes = (
        db.query(func.count(Frete.id), func.coalesce(func.sum(Frete.valor_total), 0))
        .filter(
            Frete.parceiro_id == parceiro.id,
            Frete.status != StatusFrete.CANCELADO,
            Frete.criado_em > inicio,
            Frete.criado_em <= fim,
        )
        .first()
    )

    if total_passagens == 0 and total_fretes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Não há vendas nesse período pra gerar repasse."
        )

    valor_passagens = float(valor_passagens)
    valor_fretes = float(valor_fretes)
    comissao_pct = float(parceiro.comissao_percentual) if parceiro.comissao_percentual is not None else 0.0
    valor_comissao = round((valor_passagens + valor_fretes) * comissao_pct / 100, 2)

    repasse = RepasseParceiro(
        tenant_id=usuario_atual.tenant_id,
        parceiro_id=parceiro.id,
        periodo_inicio=inicio,
        periodo_fim=fim,
        total_passagens=total_passagens,
        valor_passagens=round(valor_passagens, 2),
        total_fretes=total_fretes,
        valor_fretes=round(valor_fretes, 2),
        comissao_percentual=comissao_pct,
        valor_comissao=valor_comissao,
    )
    db.add(repasse)
    db.commit()
    db.refresh(repasse)
    return _repasse_para_out(repasse)


@router.get("/minha/repasses", response_model=list[RepasseParceiroOut])
def meus_repasses(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.PARCEIRO)),
):
    """Precisa vir registrada antes de GET /{parceiro_id}/repasses — o
    FastAPI casa rotas por posição de registro e forma do caminho, não
    pelo tipo do parâmetro, então "/minha/repasses" seria capturado pela
    rota dinâmica se ela viesse primeiro."""
    repasses = (
        db.query(RepasseParceiro)
        .filter(RepasseParceiro.parceiro_id == usuario_atual.parceiro_id)
        .order_by(RepasseParceiro.criado_em.desc())
        .all()
    )
    return [_repasse_para_out(r) for r in repasses]


@router.get("/{parceiro_id}/repasses", response_model=list[RepasseParceiroOut])
def listar_repasses(
    parceiro_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    parceiro = _buscar_parceiro_da_empresa(db, parceiro_id, usuario_atual)
    repasses = (
        db.query(RepasseParceiro)
        .filter(RepasseParceiro.parceiro_id == parceiro.id)
        .order_by(RepasseParceiro.criado_em.desc())
        .all()
    )
    return [_repasse_para_out(r) for r in repasses]


@router.patch("/repasses/{repasse_id}/pagar", response_model=RepasseParceiroOut)
def marcar_repasse_pago(
    repasse_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    repasse = db.get(RepasseParceiro, repasse_id)
    if not repasse or repasse.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repasse não encontrado")
    if repasse.status == StatusRepasse.PAGO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Esse repasse já foi marcado como pago.")
    repasse.status = StatusRepasse.PAGO
    repasse.pago_em = datetime.now(timezone.utc)
    db.commit()
    db.refresh(repasse)
    return _repasse_para_out(repasse)


@router.get("/minha/resumo", response_model=ResumoParceiroOut)
def meu_resumo(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.PARCEIRO)),
):
    parceiro = db.get(Parceiro, usuario_atual.parceiro_id)
    if not parceiro:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parceiro não encontrado")

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

    total_arrecadado_passagens = float(total_arrecadado_passagens)
    total_arrecadado_fretes = float(total_arrecadado_fretes)
    comissao_pct = float(parceiro.comissao_percentual) if parceiro.comissao_percentual is not None else 0.0
    comissao_estimada = round((total_arrecadado_passagens + total_arrecadado_fretes) * comissao_pct / 100, 2)

    return ResumoParceiroOut(
        parceiro_nome=parceiro.nome,
        comissao_percentual=float(parceiro.comissao_percentual) if parceiro.comissao_percentual is not None else None,
        total_passagens=total_passagens,
        total_arrecadado_passagens=round(total_arrecadado_passagens, 2),
        total_fretes=total_fretes,
        total_arrecadado_fretes=round(total_arrecadado_fretes, 2),
        comissao_estimada=comissao_estimada,
    )


@router.get("/minha/passagens", response_model=list[PassagemOut])
def minhas_passagens_vendidas(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.PARCEIRO)),
):
    return (
        db.query(Passagem)
        .filter(Passagem.parceiro_id == usuario_atual.parceiro_id)
        .order_by(Passagem.criado_em.desc())
        .all()
    )


@router.get("/minha/fretes", response_model=list[FreteOut])
def meus_fretes_despachados(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.PARCEIRO)),
):
    fretes = (
        db.query(Frete)
        .filter(Frete.parceiro_id == usuario_atual.parceiro_id)
        .order_by(Frete.criado_em.desc())
        .all()
    )
    return [_frete_para_out(f) for f in fretes]
