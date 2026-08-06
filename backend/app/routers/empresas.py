from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_roles
from app.core.security import hash_senha
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import StatusAssinatura, UserRole
from app.models.plano import Plano
from app.models.usuario import Usuario
from app.schemas.empresa import EmpresaCreate, EmpresaOut, EmpresaUpdate, TrocarPlanoRequest
from app.schemas.usuario import FuncionarioCreate, UsuarioOut
from app.services.assinatura import atualizar_situacao_assinaturas
from app.services.auditoria import registrar as registrar_auditoria

router = APIRouter(prefix="/empresas", tags=["empresas"])


@router.post("", response_model=EmpresaOut, status_code=status.HTTP_201_CREATED)
def criar_empresa(
    dados: EmpresaCreate,
    db: Session = Depends(get_db),
    _usuario=Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    if db.query(Empresa).filter(Empresa.cnpj == dados.cnpj).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CNPJ já cadastrado")
    if dados.plano_id and not db.get(Plano, dados.plano_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano não encontrado")

    empresa = Empresa(**dados.model_dump())
    db.add(empresa)
    db.commit()
    db.refresh(empresa)
    return empresa


@router.get("", response_model=list[EmpresaOut])
def listar_empresas(
    db: Session = Depends(get_db),
    _usuario=Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    atualizar_situacao_assinaturas(db)
    return db.query(Empresa).options(joinedload(Empresa.plano)).order_by(Empresa.nome).all()


def _buscar_empresa_ou_404(db: Session, empresa_id: int) -> Empresa:
    empresa = db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa não encontrada")
    return empresa


@router.patch("/{empresa_id}", response_model=EmpresaOut)
def editar_empresa(
    empresa_id: int,
    dados: EmpresaUpdate,
    db: Session = Depends(get_db),
    _usuario=Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    empresa = _buscar_empresa_ou_404(db, empresa_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(empresa, campo, valor)
    db.commit()
    db.refresh(empresa)
    return empresa


@router.patch("/{empresa_id}/desativar", response_model=EmpresaOut)
def desativar_empresa(
    empresa_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    empresa = _buscar_empresa_ou_404(db, empresa_id)
    empresa.ativo = False
    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="desativacao_empresa",
        entidade_tipo="empresa",
        entidade_id=empresa.id,
        detalhes=f"Empresa {empresa.nome} desativada",
        tenant_id=empresa.id,
    )
    db.commit()
    db.refresh(empresa)
    return empresa


@router.patch("/{empresa_id}/ativar", response_model=EmpresaOut)
def ativar_empresa(
    empresa_id: int,
    db: Session = Depends(get_db),
    _usuario=Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    empresa = _buscar_empresa_ou_404(db, empresa_id)
    empresa.ativo = True
    db.commit()
    db.refresh(empresa)
    return empresa


@router.patch("/{empresa_id}/plano", response_model=EmpresaOut)
def trocar_plano(
    empresa_id: int,
    dados: TrocarPlanoRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    empresa = _buscar_empresa_ou_404(db, empresa_id)
    plano = db.get(Plano, dados.plano_id)
    if not plano:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano não encontrado")

    empresa.plano_id = plano.id
    if empresa.status_assinatura in (StatusAssinatura.SUSPENSA, StatusAssinatura.CANCELADA):
        empresa.status_assinatura = StatusAssinatura.ATIVA

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="troca_plano",
        entidade_tipo="empresa",
        entidade_id=empresa.id,
        detalhes=f"Empresa {empresa.nome} -> plano {plano.nome}",
        tenant_id=empresa.id,
    )

    db.commit()
    db.refresh(empresa)
    return empresa


@router.post("/{empresa_id}/admin", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def criar_admin_empresa(
    empresa_id: int,
    dados: FuncionarioCreate,
    db: Session = Depends(get_db),
    _usuario=Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    empresa = _buscar_empresa_ou_404(db, empresa_id)
    if db.query(Usuario).filter(Usuario.email == dados.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado")

    usuario = Usuario(
        tenant_id=empresa.id,
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
        role=UserRole.ADMIN_EMPRESA,
        telefone=dados.telefone,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario
