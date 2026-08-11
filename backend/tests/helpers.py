from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.security import hash_senha
from app.models.empresa import Empresa
from app.models.enums import TipoOnibus, UserRole
from app.models.onibus import Onibus, PoltronaOnibus
from app.models.parada import Parada
from app.models.poltrona_viagem import PoltronaViagem
from app.models.rota import Rota
from app.models.usuario import Usuario
from app.models.viagem import Viagem


def criar_empresa_completa(db: Session, sufixo: str, total_poltronas: int = 4):
    """Cria uma empresa com admin, funcionário, ônibus, rota simples (2
    paradas) e uma viagem. Retorna um dict com tudo (ids e senhas)."""
    empresa = Empresa(nome=f"Empresa {sufixo}", cnpj=f"00.000.000/000{sufixo}-00")
    db.add(empresa)
    db.flush()

    admin = Usuario(
        tenant_id=empresa.id,
        nome=f"Admin {sufixo}",
        email=f"admin{sufixo}@teste.com",
        senha_hash=hash_senha("senha123"),
        role=UserRole.ADMIN_EMPRESA,
    )
    funcionario = Usuario(
        tenant_id=empresa.id,
        nome=f"Funcionario {sufixo}",
        email=f"func{sufixo}@teste.com",
        senha_hash=hash_senha("senha123"),
        role=UserRole.FUNCIONARIO,
    )
    db.add_all([admin, funcionario])
    db.flush()

    onibus = Onibus(tenant_id=empresa.id, identificacao=f"BUS-{sufixo}", tipo=TipoOnibus.CONVENCIONAL)
    db.add(onibus)
    db.flush()
    for i in range(1, total_poltronas + 1):
        db.add(PoltronaOnibus(onibus_id=onibus.id, numero=str(i), andar=1, fileira=i, coluna=1))
    db.flush()

    rota = Rota(tenant_id=empresa.id, origem=f"Origem{sufixo}", destino=f"Destino{sufixo}")
    db.add(rota)
    db.flush()
    db.add(Parada(rota_id=rota.id, nome=f"Origem{sufixo}", ordem=0, peso_proximo=1.0))
    db.add(Parada(rota_id=rota.id, nome=f"Destino{sufixo}", ordem=1, peso_proximo=None))
    db.flush()

    viagem = Viagem(
        tenant_id=empresa.id,
        rota_id=rota.id,
        onibus_id=onibus.id,
        data_hora_partida=datetime.now() + timedelta(days=1),
        preco=100.0,
    )
    db.add(viagem)
    db.flush()
    for p in db.query(PoltronaOnibus).filter(PoltronaOnibus.onibus_id == onibus.id).all():
        db.add(PoltronaViagem(viagem_id=viagem.id, poltrona_onibus_id=p.id))

    db.commit()

    return {
        "empresa_id": empresa.id,
        "admin_email": admin.email,
        "funcionario_email": funcionario.email,
        "senha": "senha123",
        "onibus_id": onibus.id,
        "rota_id": rota.id,
        "viagem_id": viagem.id,
    }


def criar_rota_com_paradas(db: Session, empresa_id: int, nomes_pesos: list[tuple[str, float | None]]) -> Rota:
    """nomes_pesos: lista de (nome, peso_proximo) em ordem, último com peso None."""
    rota = Rota(tenant_id=empresa_id, origem=nomes_pesos[0][0], destino=nomes_pesos[-1][0])
    db.add(rota)
    db.flush()
    for ordem, (nome, peso) in enumerate(nomes_pesos):
        db.add(Parada(rota_id=rota.id, nome=nome, ordem=ordem, peso_proximo=peso))
    db.commit()
    db.refresh(rota)
    return rota


def criar_super_admin(db: Session, sufixo: str) -> dict:
    admin = Usuario(
        tenant_id=None,
        nome=f"Super {sufixo}",
        email=f"super{sufixo}@teste.com",
        senha_hash=hash_senha("senha123"),
        role=UserRole.SUPER_ADMIN,
    )
    db.add(admin)
    db.commit()
    return {"email": admin.email, "senha": "senha123"}


def criar_cliente(db: Session, sufixo: str) -> dict:
    """Cria uma conta de cliente direto no banco — evita depender do
    endpoint público /auth/registrar-cliente nos testes, que tem rate
    limit global (5 chamadas/10min) compartilhado entre toda a sessão de
    testes e estouraria com facilidade se vários arquivos registrarem
    clientes."""
    cliente = Usuario(
        tenant_id=None,
        nome=f"Cliente {sufixo}",
        email=f"cliente{sufixo}@teste.com",
        senha_hash=hash_senha("senha123"),
        role=UserRole.CLIENTE,
        documento="444.444.444-44",
    )
    db.add(cliente)
    db.commit()
    return {"email": cliente.email, "senha": "senha123"}


def login(client, email: str, senha: str) -> str:
    resposta = client.post("/api/auth/login", json={"email": email, "senha": senha})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
