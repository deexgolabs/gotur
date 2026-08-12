from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles, require_staff
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import TipoRastreioPush, UserRole
from app.models.frete import Frete, PosicaoFrete
from app.models.motorista import Motorista
from app.models.parceiro import Parceiro
from app.models.usuario import Usuario
from app.schemas.fretamento import PosicaoCreate, PosicaoOut
from app.schemas.frete import (
    FreteCreate,
    FreteOut,
    FreteUpdate,
    MudarStatusFreteRequest,
    RastreioFretePublicoOut,
    SolicitarFreteRequest,
)
from app.schemas.push import InscricaoPushRequest
from app.services.auditoria import registrar as registrar_auditoria
from app.services.codigo import gerar_localizador
from app.services.geo import distancia_percorrida_km
from app.services.notificacoes import enviar_atualizacao_status_frete
from app.services.push_service import inscrever as inscrever_push
from app.services.push_service import notificar_inscritos
from app.services.rate_limit import limitar_taxa
from app.services.whatsapp_service import ROTULOS_STATUS_FRETE, enviar_atualizacao_status_frete_whatsapp

router = APIRouter(prefix="/fretes", tags=["fretes"])

_limite_solicitar_frete = limitar_taxa("solicitar-frete", max_chamadas=5, janela_segundos=600)
_limite_inscrever_push = limitar_taxa("inscrever-push-frete", max_chamadas=10, janela_segundos=600)


def _calcular_valor_total(distancia_km: float | None, valor_por_km: float | None, valor_total_manual: float | None) -> float | None:
    if valor_total_manual is not None:
        return round(float(valor_total_manual), 2)
    if distancia_km is not None and valor_por_km is not None:
        return round(float(distancia_km) * float(valor_por_km), 2)
    return None


def _gerar_codigo_rastreio(db: Session) -> str:
    codigo = gerar_localizador(10)
    while db.query(Frete).filter(Frete.codigo_rastreio == codigo).first():
        codigo = gerar_localizador(10)
    return codigo


def _resolver_motorista_nome(db: Session, motorista_id: int | None, motorista_nome: str | None, tenant_id: int) -> str | None:
    """Se `motorista_id` foi informado, valida que pertence à empresa e
    devolve o nome dele (sobrepondo qualquer texto livre)."""
    if motorista_id is None:
        return motorista_nome
    motorista = db.get(Motorista, motorista_id)
    if not motorista or motorista.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Motorista não encontrado")
    return motorista.nome


def _para_out(frete: Frete) -> FreteOut:
    pontos = [(float(p.latitude), float(p.longitude)) for p in frete.posicoes]
    ultima = frete.posicoes[-1] if frete.posicoes else None
    return FreteOut(
        id=frete.id,
        codigo_rastreio=frete.codigo_rastreio,
        remetente_nome=frete.remetente_nome,
        remetente_contato=frete.remetente_contato,
        destinatario_nome=frete.destinatario_nome,
        destinatario_contato=frete.destinatario_contato,
        descricao_carga=frete.descricao_carga,
        origem=frete.origem,
        destino=frete.destino,
        data_hora_coleta=frete.data_hora_coleta,
        data_hora_entrega_prevista=frete.data_hora_entrega_prevista,
        motorista_nome=frete.motorista_nome,
        motorista_id=frete.motorista_id,
        veiculo_descricao=frete.veiculo_descricao,
        distancia_km=float(frete.distancia_km) if frete.distancia_km is not None else None,
        valor_por_km=float(frete.valor_por_km) if frete.valor_por_km is not None else None,
        valor_total=float(frete.valor_total) if frete.valor_total is not None else None,
        peso_kg=float(frete.peso_kg) if frete.peso_kg is not None else None,
        quantidade_volumes=frete.quantidade_volumes,
        valor_declarado=float(frete.valor_declarado) if frete.valor_declarado is not None else None,
        parceiro_id=frete.parceiro_id,
        status=frete.status,
        icone_mapa=frete.icone_mapa,
        observacoes=frete.observacoes,
        criado_em=frete.criado_em,
        distancia_percorrida_km=distancia_percorrida_km(pontos),
        ultima_posicao=PosicaoOut.model_validate(ultima) if ultima else None,
    )


@router.post("", response_model=FreteOut, status_code=status.HTTP_201_CREATED)
def criar_frete(
    dados: FreteCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    empresa = db.get(Empresa, usuario_atual.tenant_id)
    if not empresa.frete_habilitado:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="O módulo de frete não está habilitado para sua empresa")

    if dados.parceiro_id is not None:
        parceiro = db.get(Parceiro, dados.parceiro_id)
        if not parceiro or parceiro.tenant_id != usuario_atual.tenant_id or not parceiro.despacha_frete:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parceiro inválido para despacho de frete")

    motorista_nome = _resolver_motorista_nome(db, dados.motorista_id, dados.motorista_nome, usuario_atual.tenant_id)

    frete = Frete(
        tenant_id=usuario_atual.tenant_id,
        codigo_rastreio=_gerar_codigo_rastreio(db),
        remetente_nome=dados.remetente_nome,
        remetente_contato=dados.remetente_contato,
        destinatario_nome=dados.destinatario_nome,
        destinatario_contato=dados.destinatario_contato,
        descricao_carga=dados.descricao_carga,
        origem=dados.origem,
        destino=dados.destino,
        data_hora_coleta=dados.data_hora_coleta,
        data_hora_entrega_prevista=dados.data_hora_entrega_prevista,
        motorista_nome=motorista_nome,
        motorista_id=dados.motorista_id,
        veiculo_descricao=dados.veiculo_descricao,
        icone_mapa=dados.icone_mapa or "🚚",
        distancia_km=dados.distancia_km,
        valor_por_km=dados.valor_por_km,
        valor_total=_calcular_valor_total(dados.distancia_km, dados.valor_por_km, dados.valor_total),
        peso_kg=dados.peso_kg,
        quantidade_volumes=dados.quantidade_volumes,
        valor_declarado=dados.valor_declarado,
        parceiro_id=dados.parceiro_id,
        observacoes=dados.observacoes,
    )
    db.add(frete)

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="criacao_frete",
        entidade_tipo="frete",
        detalhes=f"Remetente {dados.remetente_nome}, {dados.origem} -> {dados.destino}",
        tenant_id=usuario_atual.tenant_id,
    )

    db.commit()
    db.refresh(frete)
    return _para_out(frete)


@router.post(
    "/loja/{slug}/solicitar",
    response_model=RastreioFretePublicoOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_limite_solicitar_frete)],
)
def solicitar_frete(slug: str, dados: SolicitarFreteRequest, db: Session = Depends(get_db)):
    """Sem autenticação — formulário "Enviar encomenda" da loja
    white-label. Cria uma solicitação (status SOLICITADO) pra empresa dona
    do slug; a equipe assume o atendimento depois em Fretes."""
    empresa = db.query(Empresa).filter(Empresa.slug == slug, Empresa.ativo.is_(True)).first()
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja não encontrada")
    if not empresa.frete_habilitado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Essa empresa não oferece frete")

    frete = Frete(
        tenant_id=empresa.id,
        codigo_rastreio=_gerar_codigo_rastreio(db),
        remetente_nome=dados.remetente_nome,
        remetente_contato=dados.remetente_contato,
        destinatario_nome=dados.destinatario_nome,
        destinatario_contato=dados.destinatario_contato,
        descricao_carga=dados.descricao_carga,
        origem=dados.origem,
        destino=dados.destino,
        data_hora_coleta=dados.data_hora_coleta,
        peso_kg=dados.peso_kg,
        quantidade_volumes=dados.quantidade_volumes,
        valor_declarado=dados.valor_declarado,
        observacoes=dados.observacoes,
    )
    db.add(frete)
    db.commit()
    db.refresh(frete)

    return RastreioFretePublicoOut(
        codigo_rastreio=frete.codigo_rastreio,
        remetente_nome=frete.remetente_nome,
        destinatario_nome=frete.destinatario_nome,
        origem=frete.origem,
        destino=frete.destino,
        data_hora_coleta=frete.data_hora_coleta,
        status=frete.status,
        icone_mapa=frete.icone_mapa,
        distancia_percorrida_km=0.0,
        ultima_posicao=None,
        trajeto=[],
    )


@router.get("", response_model=list[FreteOut])
def listar_fretes(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    fretes = (
        db.query(Frete)
        .options(joinedload(Frete.posicoes))
        .filter(Frete.tenant_id == usuario_atual.tenant_id)
        .order_by(Frete.data_hora_coleta.desc())
        .all()
    )
    return [_para_out(f) for f in fretes]


def _buscar_frete_da_empresa(db: Session, frete_id: int, usuario_atual: Usuario) -> Frete:
    frete = db.query(Frete).options(joinedload(Frete.posicoes)).filter(Frete.id == frete_id).first()
    if not frete or frete.tenant_id != usuario_atual.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Frete não encontrado")
    return frete


@router.get("/{frete_id}", response_model=FreteOut)
def detalhar_frete(
    frete_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    frete = _buscar_frete_da_empresa(db, frete_id, usuario_atual)
    return _para_out(frete)


@router.patch("/{frete_id}", response_model=FreteOut)
def editar_frete(
    frete_id: int,
    dados: FreteUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    frete = _buscar_frete_da_empresa(db, frete_id, usuario_atual)

    campos = dados.model_dump(exclude_unset=True)
    valor_total_manual = campos.pop("valor_total", None)
    if "motorista_id" in campos:
        campos["motorista_nome"] = _resolver_motorista_nome(
            db, campos["motorista_id"], campos.get("motorista_nome"), usuario_atual.tenant_id
        )
    for campo, valor in campos.items():
        setattr(frete, campo, valor)

    frete.valor_total = _calcular_valor_total(frete.distancia_km, frete.valor_por_km, valor_total_manual)

    db.commit()
    db.refresh(frete)
    return _para_out(frete)


def _notificar_mudanca_status(request: Request, db: Session, frete: Frete) -> None:
    empresa = db.get(Empresa, frete.tenant_id)
    slug = empresa.slug if empresa else None
    base = str(request.base_url).rstrip("/")
    link_acompanhar = f"{base}/loja/{slug}?frete={frete.codigo_rastreio}" if slug else f"{base}/rastrear-frete.html?codigo={frete.codigo_rastreio}"

    contato = (frete.destinatario_contato or frete.remetente_contato or "").strip()
    if contato:
        if "@" in contato:
            enviar_atualizacao_status_frete(
                destinatario_email=contato,
                nome=frete.destinatario_nome,
                origem=frete.origem,
                destino=frete.destino,
                novo_status=frete.status.value,
                link_acompanhar=link_acompanhar,
            )
        else:
            enviar_atualizacao_status_frete_whatsapp(
                telefone=contato,
                nome=frete.destinatario_nome,
                origem=frete.origem,
                destino=frete.destino,
                novo_status=frete.status.value,
                link_acompanhar=link_acompanhar,
            )

    rotulo_status = ROTULOS_STATUS_FRETE.get(frete.status.value, frete.status.value)
    notificar_inscritos(
        db,
        tipo=TipoRastreioPush.FRETE,
        objeto_id=frete.id,
        titulo="Frete atualizado",
        corpo=f"{frete.origem} → {frete.destino}: {rotulo_status}",
        url=link_acompanhar,
    )


@router.patch("/{frete_id}/status", response_model=FreteOut)
def mudar_status_frete(
    frete_id: int,
    dados: MudarStatusFreteRequest,
    request: Request,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    frete = _buscar_frete_da_empresa(db, frete_id, usuario_atual)
    frete.status = dados.status

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="status_frete",
        entidade_tipo="frete",
        entidade_id=frete.id,
        detalhes=f"Frete #{frete.id} -> {dados.status.value}",
        tenant_id=usuario_atual.tenant_id,
    )

    db.commit()
    db.refresh(frete)
    _notificar_mudanca_status(request, db, frete)
    return _para_out(frete)


@router.post("/{frete_id}/posicoes", response_model=PosicaoOut, status_code=status.HTTP_201_CREATED)
def registrar_posicao(
    frete_id: int,
    dados: PosicaoCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    """Enviado pelo celular do motorista enquanto o frete está em
    trânsito — mesmo padrão do fretamento."""
    frete = _buscar_frete_da_empresa(db, frete_id, usuario_atual)

    posicao = PosicaoFrete(frete_id=frete.id, latitude=dados.latitude, longitude=dados.longitude)
    db.add(posicao)
    db.commit()
    db.refresh(posicao)
    return posicao


@router.get("/{frete_id}/posicoes", response_model=list[PosicaoOut])
def listar_posicoes(
    frete_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    frete = _buscar_frete_da_empresa(db, frete_id, usuario_atual)
    return frete.posicoes


@router.get("/rastrear/{codigo}", response_model=RastreioFretePublicoOut)
def rastrear_publico(codigo: str, db: Session = Depends(get_db)):
    """Sem autenticação — link que remetente/destinatário usam pra
    acompanhar a encomenda ao vivo."""
    frete = (
        db.query(Frete)
        .options(joinedload(Frete.posicoes))
        .filter(Frete.codigo_rastreio == codigo.upper())
        .first()
    )
    if not frete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Código de rastreio não encontrado")

    pontos = [(float(p.latitude), float(p.longitude)) for p in frete.posicoes]
    ultima = frete.posicoes[-1] if frete.posicoes else None

    return RastreioFretePublicoOut(
        codigo_rastreio=frete.codigo_rastreio,
        remetente_nome=frete.remetente_nome,
        destinatario_nome=frete.destinatario_nome,
        origem=frete.origem,
        destino=frete.destino,
        data_hora_coleta=frete.data_hora_coleta,
        status=frete.status,
        icone_mapa=frete.icone_mapa,
        distancia_percorrida_km=distancia_percorrida_km(pontos),
        ultima_posicao=PosicaoOut.model_validate(ultima) if ultima else None,
        trajeto=[PosicaoOut.model_validate(p) for p in frete.posicoes],
    )


@router.post("/rastrear/{codigo}/push", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(_limite_inscrever_push)])
def inscrever_push_frete(codigo: str, dados: InscricaoPushRequest, db: Session = Depends(get_db)):
    """Sem autenticação — quem está acompanhando pela tela de rastreio
    ativa notificações do navegador pra esse frete específico."""
    frete = db.query(Frete).filter(Frete.codigo_rastreio == codigo.upper()).first()
    if not frete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Código de rastreio não encontrado")

    inscrever_push(db, tenant_id=frete.tenant_id, tipo=TipoRastreioPush.FRETE, objeto_id=frete.id, dados=dados)
