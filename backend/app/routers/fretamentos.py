from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles, require_staff
from app.database import get_db
from app.models.avaliacao import Avaliacao
from app.models.empresa import Empresa
from app.models.enums import StatusFretamento, UserRole
from app.models.fretamento import Fretamento, PosicaoFretamento
from app.models.onibus import Onibus
from app.models.usuario import Usuario
from app.schemas.avaliacao import AvaliacaoOut, AvaliarRequest
from app.schemas.fretamento import (
    FretamentoCreate,
    FretamentoOut,
    FretamentoUpdate,
    MudarStatusFretamentoRequest,
    PosicaoCreate,
    PosicaoOut,
    RastreioPublicoOut,
)
from app.services.auditoria import registrar as registrar_auditoria
from app.services.codigo import gerar_localizador
from app.services.geo import distancia_percorrida_km

router = APIRouter(prefix="/fretamentos", tags=["fretamentos"])


def _calcular_valor_total(distancia_km: float | None, valor_por_km: float | None, valor_total_manual: float | None) -> float | None:
    if valor_total_manual is not None:
        return round(float(valor_total_manual), 2)
    if distancia_km is not None and valor_por_km is not None:
        return round(float(distancia_km) * float(valor_por_km), 2)
    return None


def _gerar_codigo_rastreio(db: Session) -> str:
    codigo = gerar_localizador(10)
    while db.query(Fretamento).filter(Fretamento.codigo_rastreio == codigo).first():
        codigo = gerar_localizador(10)
    return codigo


def _para_out(fretamento: Fretamento) -> FretamentoOut:
    pontos = [(float(p.latitude), float(p.longitude)) for p in fretamento.posicoes]
    ultima = fretamento.posicoes[-1] if fretamento.posicoes else None
    return FretamentoOut(
        id=fretamento.id,
        codigo_rastreio=fretamento.codigo_rastreio,
        cliente_nome=fretamento.cliente_nome,
        cliente_documento=fretamento.cliente_documento,
        cliente_contato=fretamento.cliente_contato,
        origem=fretamento.origem,
        destino=fretamento.destino,
        data_hora_saida=fretamento.data_hora_saida,
        data_hora_retorno_prevista=fretamento.data_hora_retorno_prevista,
        onibus_id=fretamento.onibus_id,
        onibus_identificacao=fretamento.onibus.identificacao if fretamento.onibus else None,
        motorista_nome=fretamento.motorista_nome,
        distancia_km=float(fretamento.distancia_km) if fretamento.distancia_km is not None else None,
        valor_por_km=float(fretamento.valor_por_km) if fretamento.valor_por_km is not None else None,
        valor_total=float(fretamento.valor_total) if fretamento.valor_total is not None else None,
        status=fretamento.status,
        observacoes=fretamento.observacoes,
        criado_em=fretamento.criado_em,
        distancia_percorrida_km=distancia_percorrida_km(pontos),
        ultima_posicao=PosicaoOut.model_validate(ultima) if ultima else None,
    )


@router.post("", response_model=FretamentoOut, status_code=status.HTTP_201_CREATED)
def criar_fretamento(
    dados: FretamentoCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    if dados.onibus_id:
        onibus = db.get(Onibus, dados.onibus_id)
        if not onibus or onibus.tenant_id != usuario_atual.tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ônibus não encontrado")

    empresa = db.get(Empresa, usuario_atual.tenant_id)
    valor_por_km = dados.valor_por_km if dados.valor_por_km is not None else empresa.preco_km_fretamento

    fretamento = Fretamento(
        tenant_id=usuario_atual.tenant_id,
        codigo_rastreio=_gerar_codigo_rastreio(db),
        cliente_nome=dados.cliente_nome,
        cliente_documento=dados.cliente_documento,
        cliente_contato=dados.cliente_contato,
        origem=dados.origem,
        destino=dados.destino,
        data_hora_saida=dados.data_hora_saida,
        data_hora_retorno_prevista=dados.data_hora_retorno_prevista,
        onibus_id=dados.onibus_id,
        motorista_nome=dados.motorista_nome,
        distancia_km=dados.distancia_km,
        valor_por_km=valor_por_km,
        valor_total=_calcular_valor_total(dados.distancia_km, valor_por_km, dados.valor_total),
        observacoes=dados.observacoes,
    )
    db.add(fretamento)

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="criacao_fretamento",
        entidade_tipo="fretamento",
        detalhes=f"Cliente {dados.cliente_nome}, {dados.origem} -> {dados.destino}",
        tenant_id=usuario_atual.tenant_id,
    )

    db.commit()
    db.refresh(fretamento)
    return _para_out(fretamento)


@router.get("", response_model=list[FretamentoOut])
def listar_fretamentos(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    fretamentos = (
        db.query(Fretamento)
        .options(joinedload(Fretamento.onibus), joinedload(Fretamento.posicoes))
        .filter(Fretamento.tenant_id == usuario_atual.tenant_id)
        .order_by(Fretamento.data_hora_saida.desc())
        .all()
    )
    return [_para_out(f) for f in fretamentos]


def _buscar_fretamento_da_empresa(db: Session, fretamento_id: int, usuario_atual: Usuario) -> Fretamento:
    fretamento = (
        db.query(Fretamento)
        .options(joinedload(Fretamento.onibus), joinedload(Fretamento.posicoes))
        .filter(Fretamento.id == fretamento_id)
        .first()
    )
    if not fretamento or fretamento.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fretamento não encontrado")
    return fretamento


@router.get("/{fretamento_id}", response_model=FretamentoOut)
def detalhar_fretamento(
    fretamento_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    fretamento = _buscar_fretamento_da_empresa(db, fretamento_id, usuario_atual)
    return _para_out(fretamento)


@router.patch("/{fretamento_id}", response_model=FretamentoOut)
def editar_fretamento(
    fretamento_id: int,
    dados: FretamentoUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    fretamento = _buscar_fretamento_da_empresa(db, fretamento_id, usuario_atual)

    if dados.onibus_id is not None:
        onibus = db.get(Onibus, dados.onibus_id)
        if not onibus or onibus.tenant_id != usuario_atual.tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ônibus não encontrado")

    campos = dados.model_dump(exclude_unset=True)
    valor_total_manual = campos.pop("valor_total", None)
    for campo, valor in campos.items():
        setattr(fretamento, campo, valor)

    fretamento.valor_total = _calcular_valor_total(fretamento.distancia_km, fretamento.valor_por_km, valor_total_manual)

    db.commit()
    db.refresh(fretamento)
    return _para_out(fretamento)


@router.patch("/{fretamento_id}/status", response_model=FretamentoOut)
def mudar_status_fretamento(
    fretamento_id: int,
    dados: MudarStatusFretamentoRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    fretamento = _buscar_fretamento_da_empresa(db, fretamento_id, usuario_atual)
    fretamento.status = dados.status

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="status_fretamento",
        entidade_tipo="fretamento",
        entidade_id=fretamento.id,
        detalhes=f"Fretamento #{fretamento.id} -> {dados.status.value}",
        tenant_id=usuario_atual.tenant_id,
    )

    db.commit()
    db.refresh(fretamento)
    return _para_out(fretamento)


@router.post("/{fretamento_id}/posicoes", response_model=PosicaoOut, status_code=status.HTTP_201_CREATED)
def registrar_posicao(
    fretamento_id: int,
    dados: PosicaoCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    """Enviado pelo celular de quem está acompanhando o trajeto (motorista
    ou atendente a bordo), periodicamente, enquanto o fretamento está em
    andamento."""
    fretamento = _buscar_fretamento_da_empresa(db, fretamento_id, usuario_atual)

    posicao = PosicaoFretamento(fretamento_id=fretamento.id, latitude=dados.latitude, longitude=dados.longitude)
    db.add(posicao)
    db.commit()
    db.refresh(posicao)
    return posicao


@router.get("/{fretamento_id}/posicoes", response_model=list[PosicaoOut])
def listar_posicoes(
    fretamento_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    fretamento = _buscar_fretamento_da_empresa(db, fretamento_id, usuario_atual)
    return fretamento.posicoes


@router.get("/rastrear/{codigo}", response_model=RastreioPublicoOut)
def rastrear_publico(codigo: str, db: Session = Depends(get_db)):
    """Sem autenticação — link que o cliente que contratou o fretamento usa
    para acompanhar o trajeto ao vivo."""
    fretamento = (
        db.query(Fretamento)
        .options(joinedload(Fretamento.posicoes))
        .filter(Fretamento.codigo_rastreio == codigo.upper())
        .first()
    )
    if not fretamento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Código de rastreio não encontrado")

    pontos = [(float(p.latitude), float(p.longitude)) for p in fretamento.posicoes]
    ultima = fretamento.posicoes[-1] if fretamento.posicoes else None

    return RastreioPublicoOut(
        codigo_rastreio=fretamento.codigo_rastreio,
        cliente_nome=fretamento.cliente_nome,
        origem=fretamento.origem,
        destino=fretamento.destino,
        data_hora_saida=fretamento.data_hora_saida,
        status=fretamento.status,
        distancia_percorrida_km=distancia_percorrida_km(pontos),
        ultima_posicao=PosicaoOut.model_validate(ultima) if ultima else None,
        trajeto=[PosicaoOut.model_validate(p) for p in fretamento.posicoes],
        ja_avaliado=db.query(Avaliacao).filter(Avaliacao.fretamento_id == fretamento.id).first() is not None,
    )


@router.post("/rastrear/{codigo}/avaliar", response_model=AvaliacaoOut, status_code=status.HTTP_201_CREATED)
def avaliar_fretamento_publico(codigo: str, dados: AvaliarRequest, db: Session = Depends(get_db)):
    """Sem autenticação, igual ao rastreio — o cliente que contratou o
    fretamento nem sempre tem conta no GoTur."""
    fretamento = db.query(Fretamento).filter(Fretamento.codigo_rastreio == codigo.upper()).first()
    if not fretamento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Código de rastreio não encontrado")
    if fretamento.status != StatusFretamento.CONCLUIDO:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="O fretamento ainda não foi concluído")
    if db.query(Avaliacao).filter(Avaliacao.fretamento_id == fretamento.id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este fretamento já foi avaliado")

    avaliacao = Avaliacao(
        tenant_id=fretamento.tenant_id,
        fretamento_id=fretamento.id,
        nota=dados.nota,
        comentario=dados.comentario,
    )
    db.add(avaliacao)
    db.commit()
    db.refresh(avaliacao)
    return AvaliacaoOut(
        id=avaliacao.id,
        fretamento_id=avaliacao.fretamento_id,
        nota=avaliacao.nota,
        comentario=avaliacao.comentario,
        criado_em=avaliacao.criado_em,
        cliente_nome=fretamento.cliente_nome,
        origem=fretamento.origem,
        destino=fretamento.destino,
    )
