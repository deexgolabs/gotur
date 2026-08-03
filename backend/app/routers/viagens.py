from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import StatusPoltrona, UserRole
from app.models.onibus import Onibus, PoltronaOnibus
from app.models.poltrona_viagem import PoltronaViagem
from app.models.rota import Rota
from app.models.usuario import Usuario
from app.models.viagem import Viagem
from app.schemas.viagem import ViagemBuscaOut, ViagemCreate, ViagemOut

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

    viagem = Viagem(
        tenant_id=usuario_atual.tenant_id,
        rota_id=dados.rota_id,
        onibus_id=dados.onibus_id,
        data_hora_partida=dados.data_hora_partida,
        preco=dados.preco,
    )
    db.add(viagem)
    db.flush()

    poltronas_onibus = db.query(PoltronaOnibus).filter(PoltronaOnibus.onibus_id == onibus.id).all()
    for p in poltronas_onibus:
        db.add(PoltronaViagem(viagem_id=viagem.id, poltrona_onibus_id=p.id, status=StatusPoltrona.LIVRE))

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
        .options(joinedload(Viagem.rota), joinedload(Viagem.onibus).joinedload(Onibus.poltronas))
        .filter(Viagem.tenant_id == usuario_atual.tenant_id, Viagem.ativo.is_(True))
        .order_by(Viagem.data_hora_partida)
        .all()
    )


@router.get("/buscar", response_model=list[ViagemBuscaOut])
def buscar_viagens(
    origem: str,
    destino: str,
    data: date,
    db: Session = Depends(get_db),
):
    """Busca pública (cliente não precisa estar logado) de viagens disponíveis."""
    inicio = datetime.combine(data, time.min)
    fim = datetime.combine(data, time.max)

    viagens = (
        db.query(Viagem)
        .join(Rota, Viagem.rota_id == Rota.id)
        .join(Empresa, Viagem.tenant_id == Empresa.id)
        .filter(
            Rota.origem.ilike(f"%{origem}%"),
            Rota.destino.ilike(f"%{destino}%"),
            Viagem.data_hora_partida.between(inicio, fim),
            Viagem.ativo.is_(True),
            Empresa.ativo.is_(True),
        )
        .options(joinedload(Viagem.rota), joinedload(Viagem.onibus))
        .order_by(Viagem.data_hora_partida)
        .all()
    )

    resultado = []
    for v in viagens:
        livres = (
            db.query(func.count(PoltronaViagem.id))
            .filter(PoltronaViagem.viagem_id == v.id, PoltronaViagem.status == StatusPoltrona.LIVRE)
            .scalar()
        )
        resultado.append(
            ViagemBuscaOut(
                id=v.id,
                empresa_nome=v.onibus.empresa.nome if v.onibus.empresa else "",
                data_hora_partida=v.data_hora_partida,
                preco=float(v.preco),
                origem=v.rota.origem,
                destino=v.rota.destino,
                poltronas_livres=livres,
            )
        )
    return resultado
