from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import StatusPoltrona, UserRole
from app.models.onibus import Onibus, PoltronaOnibus
from app.models.ocupacao_poltrona import OcupacaoPoltrona
from app.models.parada import Parada
from app.models.poltrona_viagem import PoltronaViagem
from app.models.rota import Rota
from app.models.usuario import Usuario
from app.models.viagem import Viagem
from app.schemas.viagem import ViagemBuscaOut, ViagemCreate, ViagemOut, ViagemUpdate
from app.services.limites_plano import verificar_limite_viagens_mes
from app.services.trecho import (
    buscar_paradas_da_rota,
    calcular_preco_trecho,
    liberar_holds_expirados,
    status_da_poltrona_no_trecho,
)

router = APIRouter(prefix="/viagens", tags=["viagens"])


@router.post("", response_model=ViagemOut, status_code=status.HTTP_201_CREATED)
def criar_viagem(
    dados: ViagemCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    rota = db.get(Rota, dados.rota_id)
    onibus = db.get(Onibus, dados.onibus_id)
    if not rota or rota.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rota não encontrada")
    if not onibus or onibus.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ônibus não encontrado")

    empresa = db.get(Empresa, usuario_atual.tenant_id)
    if not empresa.passagens_habilitado:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="O módulo de gestão de viagens não está habilitado para sua empresa")
    verificar_limite_viagens_mes(db, empresa)

    viagem = Viagem(
        tenant_id=usuario_atual.tenant_id,
        rota_id=dados.rota_id,
        onibus_id=dados.onibus_id,
        data_hora_partida=dados.data_hora_partida,
        preco=dados.preco,
        motorista_nome=dados.motorista_nome,
    )
    db.add(viagem)
    db.flush()

    poltronas_onibus = db.query(PoltronaOnibus).filter(PoltronaOnibus.onibus_id == onibus.id).all()
    for p in poltronas_onibus:
        db.add(PoltronaViagem(viagem_id=viagem.id, poltrona_onibus_id=p.id))

    db.commit()
    db.refresh(viagem)
    return viagem


@router.get("", response_model=list[ViagemOut])
def listar_viagens(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA, UserRole.FUNCIONARIO)),
):
    return (
        db.query(Viagem)
        .options(
            joinedload(Viagem.rota).joinedload(Rota.paradas),
            joinedload(Viagem.onibus).joinedload(Onibus.poltronas),
        )
        .filter(Viagem.tenant_id == usuario_atual.tenant_id)
        .order_by(Viagem.data_hora_partida)
        .all()
    )


def _buscar_viagem_da_empresa(db: Session, viagem_id: int, usuario_atual: Usuario) -> Viagem:
    viagem = db.get(Viagem, viagem_id)
    if not viagem or viagem.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem não encontrada")
    return viagem


@router.patch("/{viagem_id}", response_model=ViagemOut)
def editar_viagem(
    viagem_id: int,
    dados: ViagemUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    viagem = _buscar_viagem_da_empresa(db, viagem_id, usuario_atual)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(viagem, campo, valor)
    db.commit()
    db.refresh(viagem)
    return viagem


@router.patch("/{viagem_id}/desativar", response_model=ViagemOut)
def cancelar_viagem(
    viagem_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """Cancela a viagem (some da busca pública). Passagens já vendidas não
    são canceladas automaticamente — cancele-as separadamente se necessário."""
    viagem = _buscar_viagem_da_empresa(db, viagem_id, usuario_atual)
    viagem.ativo = False
    db.commit()
    db.refresh(viagem)
    return viagem


@router.patch("/{viagem_id}/ativar", response_model=ViagemOut)
def reativar_viagem(
    viagem_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    viagem = _buscar_viagem_da_empresa(db, viagem_id, usuario_atual)
    viagem.ativo = True
    db.commit()
    db.refresh(viagem)
    return viagem


@router.get("/loja/{slug}/cidades", response_model=list[str])
def cidades_atendidas_pela_loja(slug: str, db: Session = Depends(get_db)):
    """Sem autenticação — nomes de todas as paradas das rotas ativas dessa
    empresa, pra loja white-label oferecer origem/destino como select em
    vez de campo de texto livre (só faz sentido se a empresa já cadastrou
    rotas; a loja volta pro texto livre se a lista vier vazia)."""
    empresa = db.query(Empresa).filter(Empresa.slug == slug, Empresa.ativo.is_(True)).first()
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja não encontrada")

    nomes = (
        db.query(Parada.nome)
        .join(Rota, Parada.rota_id == Rota.id)
        .filter(Rota.tenant_id == empresa.id, Rota.ativo.is_(True))
        .distinct()
        .all()
    )
    return sorted({nome for (nome,) in nomes})


@router.get("/buscar", response_model=list[ViagemBuscaOut])
def buscar_viagens(
    origem: str,
    destino: str,
    data: date,
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
):
    """Busca pública (cliente não precisa estar logado) de viagens
    disponíveis. Casa `origem`/`destino` contra qualquer par de paradas da
    rota (na ordem certa), não só as pontas — permite comprar um trecho de
    uma viagem mais longa. `tenant_id` é opcional: usado pela loja
    white-label (/loja/{slug}) pra restringir a busca só às viagens
    daquela empresa; sem ele, busca em todas (portal genérico)."""
    inicio = datetime.combine(data, time.min)
    fim = datetime.combine(data, time.max)

    query = (
        db.query(Viagem)
        .join(Rota, Viagem.rota_id == Rota.id)
        .join(Empresa, Viagem.tenant_id == Empresa.id)
        .filter(
            Viagem.data_hora_partida.between(inicio, fim),
            Viagem.ativo.is_(True),
            Empresa.ativo.is_(True),
        )
    )
    if tenant_id is not None:
        query = query.filter(Viagem.tenant_id == tenant_id)

    viagens = (
        query.options(joinedload(Viagem.rota).joinedload(Rota.paradas), joinedload(Viagem.onibus))
        .order_by(Viagem.data_hora_partida)
        .all()
    )

    resultado = []
    for v in viagens:
        paradas = sorted(v.rota.paradas, key=lambda p: p.ordem)
        parada_origem = next((p for p in paradas if origem.lower() in p.nome.lower()), None)
        parada_destino = next((p for p in paradas if destino.lower() in p.nome.lower()), None)
        if not parada_origem or not parada_destino or parada_origem.ordem >= parada_destino.ordem:
            continue

        poltronas_viagem = db.query(PoltronaViagem).filter(PoltronaViagem.viagem_id == v.id).all()
        ids_poltronas = [p.id for p in poltronas_viagem]
        liberar_holds_expirados(db, ids_poltronas)

        ocupacoes = (
            db.query(OcupacaoPoltrona).filter(OcupacaoPoltrona.poltrona_viagem_id.in_(ids_poltronas)).all()
            if ids_poltronas
            else []
        )
        ocupacoes_por_poltrona: dict[int, list[OcupacaoPoltrona]] = {}
        for o in ocupacoes:
            ocupacoes_por_poltrona.setdefault(o.poltrona_viagem_id, []).append(o)

        livres = 0
        for pv in poltronas_viagem:
            status_pv, _ = status_da_poltrona_no_trecho(
                ocupacoes_por_poltrona.get(pv.id, []), parada_origem.ordem, parada_destino.ordem
            )
            if status_pv == StatusPoltrona.LIVRE:
                livres += 1

        resultado.append(
            ViagemBuscaOut(
                id=v.id,
                empresa_nome=v.onibus.empresa.nome if v.onibus.empresa else "",
                data_hora_partida=v.data_hora_partida,
                preco=calcular_preco_trecho(paradas, parada_origem.ordem, parada_destino.ordem, v.preco),
                origem=parada_origem.nome,
                destino=parada_destino.nome,
                parada_origem_id=parada_origem.id,
                parada_destino_id=parada_destino.id,
                poltronas_livres=livres,
            )
        )
    return resultado
