from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import criar_access_token, hash_senha, normalizar_email, verificar_senha
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import UserRole
from app.models.plano import Plano
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequest, RegistroCliente, RegistroEmpresa, TokenResponse
from app.services.rate_limit import limitar_taxa
from app.services.slug import gerar_slug_unico

router = APIRouter(prefix="/auth", tags=["auth"])

_limite_registro_empresa = limitar_taxa("registrar-empresa", max_chamadas=3, janela_segundos=1800)
_limite_registro_cliente = limitar_taxa("registrar-cliente", max_chamadas=5, janela_segundos=600)


@router.post("/login", response_model=TokenResponse)
def login(dados: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(func.lower(Usuario.email) == normalizar_email(dados.email)).first()
    if not usuario or not verificar_senha(dados.senha, usuario.senha_hash) or not usuario.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos")

    token = criar_access_token(
        {"sub": str(usuario.id), "role": usuario.role.value, "tenant_id": usuario.tenant_id}
    )
    return TokenResponse(
        access_token=token, role=usuario.role, nome=usuario.nome, tenant_id=usuario.tenant_id
    )


@router.post(
    "/registrar-empresa",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_limite_registro_empresa)],
)
def registrar_empresa(dados: RegistroEmpresa, db: Session = Depends(get_db)):
    """Cadastro público (onboarding self-service): uma viação nova se
    cadastra sozinha, escolhe o plano e já entra logada como admin da
    própria empresa, sem depender do super admin criar manualmente."""
    admin_email = normalizar_email(dados.admin_email)
    if db.query(Empresa).filter(Empresa.cnpj == dados.cnpj).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CNPJ já cadastrado")
    if db.query(Usuario).filter(func.lower(Usuario.email) == admin_email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado")

    plano = db.query(Plano).filter(Plano.id == dados.plano_id, Plano.ativo.is_(True)).first()
    if not plano:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano não encontrado")

    empresa = Empresa(
        nome=dados.empresa_nome,
        cnpj=dados.cnpj,
        email_contato=dados.empresa_email,
        plano_id=plano.id,
    )
    db.add(empresa)
    db.flush()
    empresa.slug = gerar_slug_unico(db, dados.empresa_nome)

    admin = Usuario(
        tenant_id=empresa.id,
        nome=dados.admin_nome,
        email=admin_email,
        senha_hash=hash_senha(dados.admin_senha),
        role=UserRole.ADMIN_EMPRESA,
        telefone=dados.admin_telefone,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    token = criar_access_token({"sub": str(admin.id), "role": admin.role.value, "tenant_id": admin.tenant_id})
    return TokenResponse(access_token=token, role=admin.role, nome=admin.nome, tenant_id=admin.tenant_id)


@router.post(
    "/registrar-cliente",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_limite_registro_cliente)],
)
def registrar_cliente(dados: RegistroCliente, db: Session = Depends(get_db)):
    email = normalizar_email(dados.email)
    if db.query(Usuario).filter(func.lower(Usuario.email) == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado")

    indicador_id = None
    if dados.codigo_indicacao:
        indicador = db.query(Usuario).filter(Usuario.codigo_indicacao == dados.codigo_indicacao.strip().upper()).first()
        if indicador:
            indicador_id = indicador.id

    usuario = Usuario(
        tenant_id=None,
        nome=dados.nome,
        email=email,
        senha_hash=hash_senha(dados.senha),
        role=UserRole.CLIENTE,
        documento=dados.documento,
        telefone=dados.telefone,
        indicado_por_usuario_id=indicador_id,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    token = criar_access_token(
        {"sub": str(usuario.id), "role": usuario.role.value, "tenant_id": usuario.tenant_id}
    )
    return TokenResponse(
        access_token=token, role=usuario.role, nome=usuario.nome, tenant_id=usuario.tenant_id
    )
