from app.core.security import hash_senha
from app.models.enums import UserRole
from app.models.usuario import Usuario


def test_login_e_case_insensitive_para_email(client, db):
    """Regressão: um cliente que se cadastrou como 'Fulano@Live.com' não
    conseguia logar digitando 'fulano@live.com' (ou vice-versa) — a
    comparação no banco era exata (==), e e-mail na prática não é
    case-sensitive (Gmail, Outlook etc. tratam como iguais).

    Cria o usuário direto no banco (não via /auth/registrar-cliente) pra
    não gastar cota do rate limit global desse endpoint (5 chamadas/10min,
    compartilhado por toda a sessão de testes — ver tests/helpers.py)."""
    usuario = Usuario(
        tenant_id=None,
        nome="Fulano",
        email="Fulano.Teste@Live.com",
        senha_hash=hash_senha("senha123"),
        role=UserRole.CLIENTE,
        documento="111.111.111-11",
    )
    db.add(usuario)
    db.commit()

    login_minusculo = client.post("/api/auth/login", json={"email": "fulano.teste@live.com", "senha": "senha123"})
    assert login_minusculo.status_code == 200, login_minusculo.text

    login_maiusculo = client.post("/api/auth/login", json={"email": "FULANO.TESTE@LIVE.COM", "senha": "senha123"})
    assert login_maiusculo.status_code == 200, login_maiusculo.text


def test_registrar_cliente_bloqueia_email_duplicado_com_caixa_diferente(client, db):
    """Só a segunda tentativa passa pelo endpoint público — a primeira
    conta é criada direto no banco pra gastar só 1 chamada da cota do
    rate limit global (5/10min, compartilhado por toda a sessão de
    testes; ver tests/helpers.py)."""
    usuario = Usuario(
        tenant_id=None,
        nome="Ciclano",
        email="ciclano@teste.com",
        senha_hash=hash_senha("senha123"),
        role=UserRole.CLIENTE,
        documento="222.222.222-22",
    )
    db.add(usuario)
    db.commit()

    duplicado = client.post(
        "/api/auth/registrar-cliente",
        json={"nome": "Ciclano 2", "email": "Ciclano@Teste.com", "senha": "senha123", "documento": "333.333.333-33"},
    )
    assert duplicado.status_code == 409, duplicado.text
