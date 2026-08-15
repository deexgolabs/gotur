from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import StatusPoltrona, UserRole
from app.models.evento import AssentoLocal, AssentoSessao, Local, Sessao
from app.models.usuario import Usuario
from app.schemas.evento import SessaoCreate, SessaoLojaOut, SessaoOut, SessaoUpdate

router = APIRouter(prefix="/sessoes", tags=["sessoes"])


def _exigir_modulo_eventos(empresa: Empresa) -> None:
    if not empresa.eventos_habilitado:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="O módulo de eventos não está habilitado para sua empresa")


@router.post("", response_model=SessaoOut, status_code=status.HTTP_201_CREATED)
def criar_sessao(
    dados: SessaoCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    local = db.get(Local, dados.local_id)
    if not local or local.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local não encontrado")

    empresa = db.get(Empresa, usuario_atual.tenant_id)
    _exigir_modulo_eventos(empresa)

    sessao = Sessao(
        tenant_id=usuario_atual.tenant_id,
        local_id=dados.local_id,
        nome_evento=dados.nome_evento,
        data_hora=dados.data_hora,
        preco=dados.preco,
    )
    db.add(sessao)
    db.flush()

    assentos_local = db.query(AssentoLocal).filter(AssentoLocal.local_id == local.id).all()
    for a in assentos_local:
        db.add(AssentoSessao(sessao_id=sessao.id, assento_local_id=a.id))

    db.commit()
    db.refresh(sessao)
    return sessao


@router.get("", response_model=list[SessaoOut])
def listar_sessoes(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA, UserRole.FUNCIONARIO)),
):
    return (
        db.query(Sessao)
        .options(joinedload(Sessao.local).joinedload(Local.assentos))
        .filter(Sessao.tenant_id == usuario_atual.tenant_id)
        .order_by(Sessao.data_hora)
        .all()
    )


def _buscar_sessao_da_empresa(db: Session, sessao_id: int, usuario_atual: Usuario) -> Sessao:
    sessao = db.get(Sessao, sessao_id)
    if not sessao or sessao.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessão não encontrada")
    return sessao


@router.patch("/{sessao_id}", response_model=SessaoOut)
def editar_sessao(
    sessao_id: int,
    dados: SessaoUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    sessao = _buscar_sessao_da_empresa(db, sessao_id, usuario_atual)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(sessao, campo, valor)
    db.commit()
    db.refresh(sessao)
    return sessao


@router.patch("/{sessao_id}/cancelar", response_model=SessaoOut)
def cancelar_sessao(
    sessao_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    sessao = _buscar_sessao_da_empresa(db, sessao_id, usuario_atual)
    sessao.ativo = False
    db.commit()
    db.refresh(sessao)
    return sessao


@router.get("/loja/{slug}", response_model=list[SessaoLojaOut])
def listar_sessoes_da_loja(slug: str, db: Session = Depends(get_db)):
    """Sem autenticação — sessões futuras e ativas dessa empresa, pra aba
    Eventos da loja white-label. Diferente da busca de passagem (por
    origem/destino), aqui é só "o que vai passar", sem rota."""
    empresa = db.query(Empresa).filter(Empresa.slug == slug, Empresa.ativo.is_(True)).first()
    if not empresa or not empresa.eventos_habilitado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja não encontrada")

    sessoes = (
        db.query(Sessao)
        .options(joinedload(Sessao.local))
        .filter(Sessao.tenant_id == empresa.id, Sessao.ativo.is_(True), Sessao.data_hora >= datetime.utcnow())
        .order_by(Sessao.data_hora)
        .all()
    )

    resultado = []
    for s in sessoes:
        livres = (
            db.query(AssentoSessao)
            .filter(AssentoSessao.sessao_id == s.id, AssentoSessao.status == StatusPoltrona.LIVRE)
            .count()
        )
        resultado.append(
            SessaoLojaOut(
                id=s.id,
                nome_evento=s.nome_evento,
                local_nome=s.local.nome,
                data_hora=s.data_hora,
                preco=float(s.preco),
                assentos_livres=livres,
            )
        )
    return resultado
