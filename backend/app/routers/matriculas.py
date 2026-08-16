from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_staff
from app.models.empresa import Empresa
from app.database import get_db
from app.models.enums import StatusFatura, StatusMatricula, TipoMatricula, UserRole
from app.models.academia import FaturaMatricula, Matricula
from app.models.usuario import Usuario
from app.schemas.matricula import MatriculaCreate, MatriculaLojaCreate, MatriculaOut
from app.services.limites_plano import verificar_limite_matriculas_ativas
from app.services.matricula_status import atualizar_situacao_matriculas

router = APIRouter(tags=["matriculas"])

DIAS_PARA_VENCIMENTO = 7


def _exigir_modulo_academia(empresa: Empresa) -> None:
    if not empresa.academia_habilitado:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="O módulo de academia não está habilitado para sua empresa")


def _para_out(db: Session, matricula: Matricula) -> MatriculaOut:
    cliente = db.get(Usuario, matricula.cliente_usuario_id)
    return MatriculaOut(
        id=matricula.id,
        cliente_usuario_id=matricula.cliente_usuario_id,
        cliente_nome=cliente.nome if cliente else None,
        tipo=matricula.tipo,
        valor_mensalidade=float(matricula.valor_mensalidade),
        aulas_por_ciclo=matricula.aulas_por_ciclo,
        aulas_utilizadas_ciclo_atual=matricula.aulas_utilizadas_ciclo_atual,
        status=matricula.status,
        criado_em=matricula.criado_em,
        cancelada_em=matricula.cancelada_em,
    )


def _criar_matricula_com_primeira_fatura(
    db: Session, tenant_id: int, cliente_usuario_id: int, *, tipo: TipoMatricula, valor_mensalidade: float, aulas_por_ciclo: int | None
) -> Matricula:
    if tipo == TipoMatricula.PACOTE_AULAS and not aulas_por_ciclo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe aulas_por_ciclo para matrícula por pacote")

    matricula = Matricula(
        tenant_id=tenant_id,
        cliente_usuario_id=cliente_usuario_id,
        tipo=tipo,
        valor_mensalidade=valor_mensalidade,
        aulas_por_ciclo=aulas_por_ciclo,
        status=StatusMatricula.PENDENTE,
    )
    db.add(matricula)
    db.flush()

    fatura = FaturaMatricula(
        tenant_id=tenant_id,
        matricula_id=matricula.id,
        cliente_usuario_id=cliente_usuario_id,
        valor=valor_mensalidade,
        status=StatusFatura.PENDENTE,
        vencimento=date.today() + timedelta(days=DIAS_PARA_VENCIMENTO),
    )
    db.add(fatura)

    db.commit()
    db.refresh(matricula)
    return matricula


@router.post("/matriculas", response_model=MatriculaOut, status_code=status.HTTP_201_CREATED)
def criar_matricula(
    dados: MatriculaCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    """Preço negociado pelo staff caso a caso — só esta rota aceita
    `valor_mensalidade` vindo da requisição. O autoatendimento pela loja
    (`matricular_se_pela_loja`) NUNCA deixa o cliente escolher o próprio
    preço; usa sempre `Empresa.preco_padrao_mensalidade_academia`."""
    empresa = db.get(Empresa, usuario_atual.tenant_id)
    _exigir_modulo_academia(empresa)
    verificar_limite_matriculas_ativas(db, empresa)

    cliente = db.get(Usuario, dados.cliente_usuario_id)
    if not cliente or cliente.role != UserRole.CLIENTE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")

    matricula = _criar_matricula_com_primeira_fatura(
        db, usuario_atual.tenant_id, cliente.id, tipo=dados.tipo, valor_mensalidade=dados.valor_mensalidade, aulas_por_ciclo=dados.aulas_por_ciclo
    )
    return _para_out(db, matricula)


@router.post("/matriculas/loja/{slug}", response_model=MatriculaOut, status_code=status.HTTP_201_CREATED)
def matricular_se_pela_loja(
    slug: str,
    dados: MatriculaLojaCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    if usuario_atual.role != UserRole.CLIENTE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Só clientes podem se matricular")

    empresa = db.query(Empresa).filter(Empresa.slug == slug, Empresa.ativo.is_(True)).first()
    if not empresa or not empresa.academia_habilitado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja não encontrada")
    if not empresa.preco_padrao_mensalidade_academia:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta academia ainda não configurou o preço da mensalidade pra autoatendimento. Fale com a recepção.",
        )
    verificar_limite_matriculas_ativas(db, empresa)

    matricula = _criar_matricula_com_primeira_fatura(
        db,
        empresa.id,
        usuario_atual.id,
        tipo=dados.tipo,
        valor_mensalidade=float(empresa.preco_padrao_mensalidade_academia),
        aulas_por_ciclo=dados.aulas_por_ciclo,
    )
    return _para_out(db, matricula)


@router.get("/matriculas", response_model=list[MatriculaOut])
def listar_matriculas(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    matriculas = db.query(Matricula).filter(Matricula.tenant_id == usuario_atual.tenant_id).order_by(Matricula.criado_em.desc()).all()
    return [_para_out(db, m) for m in matriculas]


@router.get("/matriculas/minhas", response_model=list[MatriculaOut])
def minhas_matriculas(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    atualizar_situacao_matriculas(db)
    matriculas = (
        db.query(Matricula)
        .filter(Matricula.cliente_usuario_id == usuario_atual.id)
        .order_by(Matricula.criado_em.desc())
        .all()
    )
    return [_para_out(db, m) for m in matriculas]


def _buscar_matricula(db: Session, matricula_id: int, usuario_atual: Usuario) -> Matricula:
    matricula = db.get(Matricula, matricula_id)
    if not matricula:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matrícula não encontrada")
    eh_staff_da_empresa = usuario_atual.role in (UserRole.FUNCIONARIO, UserRole.ADMIN_EMPRESA, UserRole.SUPER_ADMIN) and usuario_atual.tenant_id == matricula.tenant_id
    eh_dono = matricula.cliente_usuario_id == usuario_atual.id
    if not eh_staff_da_empresa and not eh_dono:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")
    return matricula


@router.patch("/matriculas/{matricula_id}/cancelar", response_model=MatriculaOut)
def cancelar_matricula(
    matricula_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    matricula = _buscar_matricula(db, matricula_id, usuario_atual)
    if matricula.status == StatusMatricula.CANCELADA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Matrícula já cancelada")

    matricula.status = StatusMatricula.CANCELADA
    matricula.cancelada_em = datetime.utcnow()

    faturas_pendentes = (
        db.query(FaturaMatricula)
        .filter(FaturaMatricula.matricula_id == matricula.id, FaturaMatricula.status == StatusFatura.PENDENTE)
        .all()
    )
    for fatura in faturas_pendentes:
        fatura.status = StatusFatura.CANCELADA

    db.commit()
    db.refresh(matricula)
    return _para_out(db, matricula)
