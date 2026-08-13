from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles, require_staff
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import CategoriaPassageiro, StatusPassagem, StatusPoltrona, TipoDocumento, TipoRastreioPush, UserRole
from app.models.motorista import Motorista
from app.models.onibus import Onibus, PoltronaOnibus
from app.models.ocupacao_poltrona import OcupacaoPoltrona
from app.models.parada import Parada
from app.models.passagem import Passagem
from app.models.poltrona_viagem import PoltronaViagem
from app.models.rota import Rota
from app.models.usuario import Usuario
from app.models.viagem import PosicaoViagem, Viagem
from app.schemas.fretamento import PosicaoCreate, PosicaoOut
from app.schemas.push import InscricaoPushRequest
from app.schemas.viagem import RastreioViagemPublicoOut, ViagemBuscaOut, ViagemCreate, ViagemMapaOut, ViagemOut, ViagemUpdate
from app.services.codigo import gerar_localizador
from app.services.geo import distancia_percorrida_km
from app.services.limites_plano import verificar_limite_viagens_mes
from app.services.pdf_service import DadosManifesto, PassageiroManifesto, gerar_manifesto_pdf
from app.services.push_service import inscrever as inscrever_push
from app.services.rate_limit import limitar_taxa
from app.services.trecho import (
    buscar_paradas_da_rota,
    calcular_preco_trecho,
    liberar_holds_expirados,
    status_da_poltrona_no_trecho,
)

ROTULOS_TIPO_DOCUMENTO = {
    TipoDocumento.CPF: "CPF",
    TipoDocumento.RG: "RG",
    TipoDocumento.CNH: "CNH",
    TipoDocumento.PASSAPORTE: "Passaporte",
    TipoDocumento.OUTRO: "Outro",
}

ROTULOS_CATEGORIA_PASSAGEIRO = {
    CategoriaPassageiro.COMUM: "Comum",
    CategoriaPassageiro.IDOSO: "Idoso",
    CategoriaPassageiro.PCD: "PCD",
    CategoriaPassageiro.CRIANCA_COLO: "Crianca de colo",
}

router = APIRouter(prefix="/viagens", tags=["viagens"])

_limite_inscrever_push_viagem = limitar_taxa("inscrever-push-viagem", max_chamadas=10, janela_segundos=600)


def _gerar_codigo_rastreio(db: Session) -> str:
    codigo = gerar_localizador(10)
    while db.query(Viagem).filter(Viagem.codigo_rastreio == codigo).first():
        codigo = gerar_localizador(10)
    return codigo


def _resolver_motorista_nome(db: Session, motorista_id: int | None, motorista_nome: str | None, tenant_id: int) -> str | None:
    """Se `motorista_id` foi informado, valida que pertence à empresa e
    devolve o nome dele (sobrepondo qualquer texto livre) — assim o
    sistema de jornada/manifesto, que ainda lê `motorista_nome`, continua
    funcionando sem alteração."""
    if motorista_id is None:
        return motorista_nome
    motorista = db.get(Motorista, motorista_id)
    if not motorista or motorista.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Motorista não encontrado")
    return motorista.nome


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

    motorista_nome = _resolver_motorista_nome(db, dados.motorista_id, dados.motorista_nome, usuario_atual.tenant_id)

    viagem = Viagem(
        tenant_id=usuario_atual.tenant_id,
        rota_id=dados.rota_id,
        onibus_id=dados.onibus_id,
        data_hora_partida=dados.data_hora_partida,
        preco=dados.preco,
        motorista_nome=motorista_nome,
        motorista_id=dados.motorista_id,
        codigo_rastreio=_gerar_codigo_rastreio(db),
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
    viagens = (
        db.query(Viagem)
        .options(
            joinedload(Viagem.rota).joinedload(Rota.paradas),
            joinedload(Viagem.onibus).joinedload(Onibus.poltronas),
        )
        .filter(Viagem.tenant_id == usuario_atual.tenant_id)
        .order_by(Viagem.data_hora_partida)
        .all()
    )
    # Viagens criadas antes do rastreamento ao vivo ainda não têm código —
    # gera na primeira vez que a lista é consultada (mesmo padrão do slug
    # de white-label da Empresa).
    sem_codigo = [v for v in viagens if not v.codigo_rastreio]
    if sem_codigo:
        for v in sem_codigo:
            v.codigo_rastreio = _gerar_codigo_rastreio(db)
        db.commit()
    return viagens


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
    campos = dados.model_dump(exclude_unset=True)
    if "motorista_id" in campos:
        campos["motorista_nome"] = _resolver_motorista_nome(
            db, campos["motorista_id"], campos.get("motorista_nome"), usuario_atual.tenant_id
        )
    for campo, valor in campos.items():
        setattr(viagem, campo, valor)
    db.commit()
    db.refresh(viagem)
    return viagem


@router.get("/{viagem_id}/manifesto.pdf")
def manifesto_pdf(
    viagem_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA, UserRole.FUNCIONARIO)),
):
    """Lista de passageiros confirmados na viagem, em PDF — pro motorista
    apresentar numa fiscalização (blitz) em linha intermunicipal."""
    viagem = (
        db.query(Viagem)
        .options(joinedload(Viagem.rota), joinedload(Viagem.onibus))
        .filter(Viagem.id == viagem_id, Viagem.tenant_id == usuario_atual.tenant_id)
        .first()
    )
    if not viagem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem não encontrada")

    passagens = (
        db.query(Passagem)
        .options(joinedload(Passagem.poltrona_viagem).joinedload(PoltronaViagem.poltrona_onibus))
        .filter(Passagem.viagem_id == viagem.id, Passagem.status == StatusPassagem.CONFIRMADA)
        .all()
    )
    passagens.sort(key=lambda p: p.poltrona_viagem.poltrona_onibus.numero)

    empresa = db.get(Empresa, usuario_atual.tenant_id)
    pdf_bytes = gerar_manifesto_pdf(
        DadosManifesto(
            empresa_nome=empresa.nome if empresa else "",
            origem=viagem.rota.origem,
            destino=viagem.rota.destino,
            data_hora_partida=viagem.data_hora_partida,
            onibus_identificacao=viagem.onibus.identificacao,
            motorista_nome=viagem.motorista_nome,
            passageiros=[
                PassageiroManifesto(
                    poltrona=p.poltrona_viagem.poltrona_onibus.numero,
                    nome=p.cliente_nome,
                    documento=p.cliente_documento,
                    tipo_documento=ROTULOS_TIPO_DOCUMENTO.get(p.tipo_documento, p.tipo_documento.value),
                    categoria=ROTULOS_CATEGORIA_PASSAGEIRO.get(p.categoria_passageiro, p.categoria_passageiro.value),
                    embarcado=p.checkin_em is not None,
                )
                for p in passagens
            ],
        )
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="manifesto-viagem-{viagem.id}.pdf"'},
    )


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


@router.post("/{viagem_id}/posicoes", response_model=PosicaoOut, status_code=status.HTTP_201_CREATED)
def registrar_posicao(
    viagem_id: int,
    dados: PosicaoCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    """Enviado pelo celular de quem está acompanhando o trajeto (motorista
    ou atendente a bordo), periodicamente, enquanto a viagem está em
    andamento — mesmo mecanismo já usado por fretamento e frete."""
    viagem = _buscar_viagem_da_empresa(db, viagem_id, usuario_atual)
    if not viagem.codigo_rastreio:
        viagem.codigo_rastreio = _gerar_codigo_rastreio(db)

    posicao = PosicaoViagem(viagem_id=viagem.id, latitude=dados.latitude, longitude=dados.longitude)
    db.add(posicao)
    db.commit()
    db.refresh(posicao)
    return posicao


@router.get("/{viagem_id}/posicoes", response_model=list[PosicaoOut])
def listar_posicoes(
    viagem_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    viagem = _buscar_viagem_da_empresa(db, viagem_id, usuario_atual)
    return viagem.posicoes


@router.get("/rastrear/{codigo}", response_model=RastreioViagemPublicoOut)
def rastrear_publico(codigo: str, db: Session = Depends(get_db)):
    """Sem autenticação — link que o cliente que comprou passagem usa pra
    acompanhar o ônibus ao vivo antes/durante o embarque."""
    viagem = (
        db.query(Viagem)
        .options(joinedload(Viagem.posicoes), joinedload(Viagem.rota))
        .filter(Viagem.codigo_rastreio == codigo.upper())
        .first()
    )
    if not viagem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Código de rastreio não encontrado")

    pontos = [(float(p.latitude), float(p.longitude)) for p in viagem.posicoes]
    ultima = viagem.posicoes[-1] if viagem.posicoes else None

    return RastreioViagemPublicoOut(
        codigo_rastreio=viagem.codigo_rastreio,
        origem=viagem.rota.origem,
        destino=viagem.rota.destino,
        data_hora_partida=viagem.data_hora_partida,
        distancia_percorrida_km=distancia_percorrida_km(pontos),
        ultima_posicao=PosicaoOut.model_validate(ultima) if ultima else None,
        trajeto=[PosicaoOut.model_validate(p) for p in viagem.posicoes],
    )


@router.post("/rastrear/{codigo}/push", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(_limite_inscrever_push_viagem)])
def inscrever_push_viagem(codigo: str, dados: InscricaoPushRequest, db: Session = Depends(get_db)):
    """Sem autenticação — quem está acompanhando pela tela de rastreio
    ativa notificações do navegador pra essa viagem específica."""
    viagem = db.query(Viagem).filter(Viagem.codigo_rastreio == codigo.upper()).first()
    if not viagem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Código de rastreio não encontrado")

    inscrever_push(db, tenant_id=viagem.tenant_id, tipo=TipoRastreioPush.VIAGEM, objeto_id=viagem.id, dados=dados)


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


@router.get("/{viagem_id}", response_model=ViagemMapaOut)
def detalhe_viagem_mapa(
    viagem_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    """Detalhe com trajeto calculado — usado pela tela interna de mapa ao
    vivo (ver /pages/mapa-viagem.html). Fica no fim do arquivo de propósito:
    é uma rota dinâmica de 1 segmento e precisa vir depois de /buscar, senão
    sombreia ela (mesmo cuidado já tomado nas outras rotas desse tipo)."""
    viagem = (
        db.query(Viagem)
        .options(joinedload(Viagem.posicoes), joinedload(Viagem.rota), joinedload(Viagem.onibus))
        .filter(Viagem.id == viagem_id, Viagem.tenant_id == usuario_atual.tenant_id)
        .first()
    )
    if not viagem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem não encontrada")

    pontos = [(float(p.latitude), float(p.longitude)) for p in viagem.posicoes]
    ultima = viagem.posicoes[-1] if viagem.posicoes else None

    return ViagemMapaOut(
        id=viagem.id,
        codigo_rastreio=viagem.codigo_rastreio,
        origem=viagem.rota.origem,
        destino=viagem.rota.destino,
        data_hora_partida=viagem.data_hora_partida,
        onibus_identificacao=viagem.onibus.identificacao if viagem.onibus else None,
        motorista_nome=viagem.motorista_nome,
        distancia_percorrida_km=distancia_percorrida_km(pontos),
        ultima_posicao=PosicaoOut.model_validate(ultima) if ultima else None,
        trajeto=[PosicaoOut.model_validate(p) for p in viagem.posicoes],
    )
