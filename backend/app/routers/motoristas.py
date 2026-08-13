from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.core.security import hash_senha
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import StatusFrete, StatusFretamento, UserRole
from app.models.frete import Frete
from app.models.fretamento import Fretamento
from app.models.motorista import Motorista
from app.models.usuario import Usuario
from app.models.viagem import Viagem
from app.schemas.motorista import (
    CriarAcessoMotoristaRequest,
    MotoristaCreate,
    MotoristaOut,
    MotoristaUpdate,
    TrajetoMotoristaOut,
)

router = APIRouter(prefix="/motoristas", tags=["motoristas"])


def _para_out(db: Session, motorista: Motorista) -> MotoristaOut:
    tem_acesso = db.query(Usuario).filter(Usuario.motorista_id == motorista.id, Usuario.ativo.is_(True)).first() is not None
    return MotoristaOut(
        id=motorista.id,
        nome=motorista.nome,
        cnh=motorista.cnh,
        categoria_cnh=motorista.categoria_cnh,
        telefone=motorista.telefone,
        ativo=motorista.ativo,
        criado_em=motorista.criado_em,
        tem_acesso=tem_acesso,
    )


@router.post("", response_model=MotoristaOut, status_code=status.HTTP_201_CREATED)
def criar_motorista(
    dados: MotoristaCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    empresa = db.get(Empresa, usuario_atual.tenant_id)
    if not empresa.motorista_habilitado:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="O módulo de motoristas não está habilitado para sua empresa")
    motorista = Motorista(tenant_id=usuario_atual.tenant_id, **dados.model_dump())
    db.add(motorista)
    db.commit()
    db.refresh(motorista)
    return _para_out(db, motorista)


@router.get("", response_model=list[MotoristaOut])
def listar_motoristas(
    apenas_ativos: bool = False,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA, UserRole.FUNCIONARIO)),
):
    """`apenas_ativos=true` é usado pelos formulários de viagem/fretamento/
    frete pra popular o seletor de motorista (sem mostrar os desativados)."""
    query = db.query(Motorista).filter(Motorista.tenant_id == usuario_atual.tenant_id)
    if apenas_ativos:
        query = query.filter(Motorista.ativo.is_(True))
    return [_para_out(db, m) for m in query.order_by(Motorista.nome).all()]


@router.get("/minha/viagens", response_model=list[TrajetoMotoristaOut])
def minha_agenda(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.MOTORISTA)),
):
    """Precisa vir registrada antes de GET/PATCH "/{motorista_id}" — mesmo
    motivo do padrão já usado em app/routers/parceiros.py (FastAPI casa
    rotas por forma do caminho, não pelo tipo do parâmetro)."""
    if not usuario_atual.motorista_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Este login não está vinculado a nenhum motorista")

    itens: list[TrajetoMotoristaOut] = []

    viagens = (
        db.query(Viagem)
        .filter(Viagem.motorista_id == usuario_atual.motorista_id, Viagem.ativo.is_(True))
        .all()
    )
    for v in viagens:
        itens.append(
            TrajetoMotoristaOut(
                tipo="viagem",
                id=v.id,
                origem=v.rota.origem if v.rota else "",
                destino=v.rota.destino if v.rota else "",
                data_hora=v.data_hora_partida,
                status="ativa",
            )
        )

    fretamentos = (
        db.query(Fretamento)
        .filter(
            Fretamento.motorista_id == usuario_atual.motorista_id,
            Fretamento.status.in_((StatusFretamento.CONFIRMADO, StatusFretamento.EM_ANDAMENTO)),
        )
        .all()
    )
    for f in fretamentos:
        itens.append(
            TrajetoMotoristaOut(
                tipo="fretamento", id=f.id, origem=f.origem, destino=f.destino, data_hora=f.data_hora_saida, status=f.status.value
            )
        )

    fretes = (
        db.query(Frete)
        .filter(Frete.motorista_id == usuario_atual.motorista_id, Frete.status.in_((StatusFrete.CONFIRMADO, StatusFrete.EM_TRANSITO)))
        .all()
    )
    for f in fretes:
        itens.append(
            TrajetoMotoristaOut(
                tipo="frete", id=f.id, origem=f.origem, destino=f.destino, data_hora=f.data_hora_coleta, status=f.status.value
            )
        )

    itens.sort(key=lambda i: i.data_hora)
    return itens


def _buscar_motorista_da_empresa(db: Session, motorista_id: int, usuario_atual: Usuario) -> Motorista:
    motorista = db.get(Motorista, motorista_id)
    if not motorista or motorista.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Motorista não encontrado")
    return motorista


@router.patch("/{motorista_id}", response_model=MotoristaOut)
def editar_motorista(
    motorista_id: int,
    dados: MotoristaUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    motorista = _buscar_motorista_da_empresa(db, motorista_id, usuario_atual)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(motorista, campo, valor)
    db.commit()
    db.refresh(motorista)
    return _para_out(db, motorista)


@router.post("/{motorista_id}/acesso", response_model=MotoristaOut, status_code=status.HTTP_201_CREATED)
def criar_acesso_motorista(
    motorista_id: int,
    dados: CriarAcessoMotoristaRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """Cria o login desse motorista — ele passa a entrar no GoTur com
    e-mail e senha próprios, direto no celular, pra controlar a própria
    jornada e checklist sem precisar do painel do admin/funcionário (ver
    GET /motoristas/minha/viagens e frontend/pages/motorista-app.html)."""
    motorista = _buscar_motorista_da_empresa(db, motorista_id, usuario_atual)
    if db.query(Usuario).filter(Usuario.email == dados.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado")

    usuario = Usuario(
        tenant_id=usuario_atual.tenant_id,
        nome=motorista.nome,
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
        role=UserRole.MOTORISTA,
        motorista_id=motorista.id,
    )
    db.add(usuario)
    db.commit()
    return _para_out(db, motorista)
