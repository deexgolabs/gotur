from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_roles, require_staff
from app.core.security import hash_senha
from app.database import get_db
from app.models.empresa import Empresa
from app.models.enums import ModoCobranca, StatusAssinatura, UserRole
from app.models.plano import Plano
from app.models.usuario import Usuario
from app.schemas.empresa import (
    ConfiguracaoEmpresaRequest,
    ConfiguracaoFidelidadeRequest,
    ConfiguracaoFretamentoRequest,
    ConfiguracaoIsencaoRequest,
    ConfiguracaoMarcaRequest,
    ConfiguracaoModulosRequest,
    ConfiguracaoPagamentoRequest,
    EmpresaCreate,
    EmpresaOut,
    EmpresaUpdate,
    LojaInfoOut,
    TrocarPlanoRequest,
)
from app.schemas.usuario import FuncionarioCreate, UsuarioOut
from app.services.assinatura import atualizar_situacao_assinaturas
from app.services.auditoria import registrar as registrar_auditoria
from app.services.logo import regenerar_icones_com_nova_cor, salvar_logo
from app.services.slug import gerar_slug_unico, slugificar

router = APIRouter(prefix="/empresas", tags=["empresas"])

TIPOS_IMAGEM_ACEITOS = {"image/png", "image/jpeg", "image/webp"}
TAMANHO_MAXIMO_LOGO_BYTES = 3 * 1024 * 1024


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


@router.patch("/{empresa_id}/isencao-cobranca", response_model=EmpresaOut)
def configurar_isencao_cobranca(
    empresa_id: int,
    dados: ConfiguracaoIsencaoRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Isenta (ou volta a cobrar) a assinatura dessa empresa no GoTur —
    pra contas de teste/demonstração que não podem gerar fatura nem ser
    suspensas por inadimplência (ver app/services/faturamento.py e
    app/services/assinatura.py). Não afeta a cobrança que a empresa faz
    dos PRÓPRIOS clientes (isso é modo_cobranca, outro campo)."""
    empresa = _buscar_empresa_ou_404(db, empresa_id)
    empresa.isento_cobranca = dados.isento_cobranca

    registrar_auditoria(
        db,
        usuario=usuario_atual,
        acao="isencao_cobranca_empresa",
        entidade_tipo="empresa",
        entidade_id=empresa.id,
        detalhes=f"Empresa {empresa.nome} -> isento_cobranca={dados.isento_cobranca}",
        tenant_id=empresa.id,
    )

    db.commit()
    db.refresh(empresa)
    return empresa


@router.get("/minha", response_model=EmpresaOut)
def minha_empresa(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    """Staff (funcionário, admin ou super admin) — funcionário precisa do
    slug pra montar o link da loja na tela de Fretamentos, por exemplo."""
    empresa = _buscar_empresa_ou_404(db, usuario_atual.tenant_id)
    if not empresa.slug:
        # Empresas criadas antes do white-label ainda não têm slug —
        # gera um automaticamente na primeira vez que alguém acessa.
        empresa.slug = gerar_slug_unico(db, empresa.nome, empresa_id_ignorar=empresa.id)
        db.commit()
        db.refresh(empresa)
    return empresa


@router.patch("/minha/marca", response_model=EmpresaOut)
def configurar_marca(
    dados: ConfiguracaoMarcaRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """Personalização white-label: slug da loja pública (/loja/{slug}) e cor
    principal usada no tema da loja e nos ícones do PWA."""
    empresa = _buscar_empresa_ou_404(db, usuario_atual.tenant_id)

    if dados.cor_primaria is not None:
        cor = dados.cor_primaria.strip()
        if cor and not (len(cor) == 7 and cor.startswith("#")):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cor deve estar no formato #rrggbb")
        empresa.cor_primaria = cor or None
        if empresa.logo_filename:
            regenerar_icones_com_nova_cor(empresa.id, empresa.cor_primaria)

    if dados.slug is not None:
        slug_normalizado = slugificar(dados.slug)
        conflito = (
            db.query(Empresa).filter(Empresa.slug == slug_normalizado, Empresa.id != empresa.id).first()
        )
        if conflito:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esse link já está em uso por outra empresa")
        empresa.slug = slug_normalizado

    db.commit()
    db.refresh(empresa)
    return empresa


@router.patch("/minha/dados", response_model=EmpresaOut)
def configurar_dados(
    dados: ConfiguracaoEmpresaRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """Dados cadastrais e textos da loja que a própria empresa pode editar
    sem depender do super admin — CNPJ fica de fora por ser documento
    legal (mudança passa pelo suporte)."""
    empresa = _buscar_empresa_ou_404(db, usuario_atual.tenant_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(empresa, campo, valor)
    db.commit()
    db.refresh(empresa)
    return empresa


@router.patch("/minha/modulos", response_model=EmpresaOut)
def configurar_modulos(
    dados: ConfiguracaoModulosRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """Liga/desliga fretamento, gestão de viagens e frete pra essa empresa
    — dentro do que o plano permitir (ver Empresa.fretamento_habilitado /
    Empresa.passagens_habilitado / Empresa.frete_habilitado)."""
    empresa = _buscar_empresa_ou_404(db, usuario_atual.tenant_id)

    if dados.fretamento_ativo is not None:
        empresa.fretamento_ativo = dados.fretamento_ativo
    if dados.passagens_ativo is not None:
        empresa.passagens_ativo = dados.passagens_ativo
    if dados.frete_ativo is not None:
        empresa.frete_ativo = dados.frete_ativo

    if not empresa.fretamento_ativo and not empresa.passagens_ativo and not empresa.frete_ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pelo menos um módulo (passagens, fretamento ou frete) precisa ficar ligado.",
        )

    db.commit()
    db.refresh(empresa)
    return empresa


@router.patch("/minha/fidelidade", response_model=EmpresaOut)
def configurar_fidelidade(
    dados: ConfiguracaoFidelidadeRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """A cada N passagens confirmadas de um cliente com conta, o sistema
    gera sozinho um cupom pessoal de desconto pra ele (ver
    app/services/fidelidade.py) — não precisa de nenhuma ação manual do
    admin depois de configurar aqui."""
    empresa = _buscar_empresa_ou_404(db, usuario_atual.tenant_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(empresa, campo, valor)
    db.commit()
    db.refresh(empresa)
    return empresa


@router.patch("/minha/pagamento", response_model=EmpresaOut)
def configurar_pagamento(
    dados: ConfiguracaoPagamentoRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """Credenciais do Mercado Pago da própria empresa + modo de cobrança
    (ver app/services/pagamento_provider.py). Com credenciais configuradas
    e modo AUTOMATICA, as vendas de passagem/frete/fretamento passam a
    cobrar de verdade via Pix e cair direto na conta Mercado Pago da
    empresa; MANUAL/DESATIVADA ignoram a credencial e mudam como a venda é
    liberada, independente de ter Mercado Pago configurado ou não."""
    empresa = _buscar_empresa_ou_404(db, usuario_atual.tenant_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(empresa, campo, valor or None)
    db.commit()
    db.refresh(empresa)
    return empresa


@router.post("/minha/logo", response_model=EmpresaOut)
async def enviar_logo(
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    empresa = _buscar_empresa_ou_404(db, usuario_atual.tenant_id)

    if arquivo.content_type not in TIPOS_IMAGEM_ACEITOS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Envie uma imagem PNG, JPEG ou WEBP")
    conteudo = await arquivo.read()
    if len(conteudo) > TAMANHO_MAXIMO_LOGO_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Imagem muito grande (máximo 3 MB)")

    try:
        versao = salvar_logo(empresa.id, conteudo, empresa.cor_primaria)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não foi possível processar essa imagem")

    empresa.logo_filename = versao
    db.commit()
    db.refresh(empresa)
    return empresa


@router.get("/loja/{slug}", response_model=LojaInfoOut)
def info_loja_publica(slug: str, db: Session = Depends(get_db)):
    """Sem autenticação — dados públicos de marca usados pela loja
    white-label (/loja/{slug}) pra se tematizar (nome, cor, logo)."""
    empresa = db.query(Empresa).filter(Empresa.slug == slug, Empresa.ativo.is_(True)).first()
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja não encontrada")
    return LojaInfoOut(
        id=empresa.id,
        nome=empresa.nome,
        slug=empresa.slug,
        cor_primaria=empresa.cor_primaria or "#6E00A7",
        logo_url=empresa.logo_url,
        telefone_contato=empresa.telefone_contato,
        texto_loja=empresa.texto_loja,
        fretamento_habilitado=empresa.fretamento_habilitado,
        passagens_habilitado=empresa.passagens_habilitado,
        frete_habilitado=empresa.frete_habilitado,
        mercadopago_public_key=empresa.mercadopago_public_key if empresa.modo_cobranca == ModoCobranca.AUTOMATICA else None,
    )


@router.patch("/minha/fretamento", response_model=EmpresaOut)
def configurar_preco_fretamento(
    dados: ConfiguracaoFretamentoRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_roles(UserRole.ADMIN_EMPRESA)),
):
    """Preço padrão por km cobrado em fretamentos — usado como valor
    sugerido quando o atendente não informa um valor específico ao criar o
    fretamento."""
    empresa = _buscar_empresa_ou_404(db, usuario_atual.tenant_id)
    empresa.preco_km_fretamento = dados.preco_km_fretamento
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
