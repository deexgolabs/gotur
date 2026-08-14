"""Cria um super admin inicial e uma empresa demo com admin, ônibus, rota e viagem.

Uso: alembic upgrade head && python seed.py
"""
from datetime import datetime, timedelta

from app.core.security import hash_senha
from app.database import SessionLocal
from app.models.empresa import Empresa
from app.models.enums import TipoOnibus, UserRole
from app.models.onibus import Onibus, PoltronaOnibus
from app.models.parada import Parada
from app.models.plano import Plano
from app.models.poltrona_viagem import PoltronaViagem
from app.models.rota import Rota
from app.models.usuario import Usuario
from app.models.viagem import Viagem

db = SessionLocal()

try:
    if not db.query(Usuario).filter(Usuario.email == "super@gotur.com").first():
        super_admin = Usuario(
            tenant_id=None,
            nome="Super Admin GoTur",
            email="super@gotur.com",
            senha_hash=hash_senha("super123"),
            role=UserRole.SUPER_ADMIN,
        )
        db.add(super_admin)
        print("Super admin criado: super@gotur.com / super123")
    else:
        print("Super admin já existe.")

    if not db.query(Plano).filter(Plano.nome == "Essencial").first():
        db.add(
            Plano(
                nome="Essencial",
                descricao="Pra quem tá começando a vender passagem online: controle de poltrona e venda, sem os módulos extras.",
                preco_mensal=99.00,
                max_onibus=3,
                max_funcionarios=5,
                max_viagens_mes=60,
                modulo_passagens=True,
                modulo_fretamento=False,
                modulo_frete=False,
                modulo_frota=False,
                modulo_motorista=False,
                modulo_dre=False,
                modulo_white_label=False,
                modulo_nfse=False,
            )
        )
        print("Plano Essencial criado (R$ 99/mês)")

    if not db.query(Plano).filter(Plano.nome == "Profissional").first():
        db.add(
            Plano(
                nome="Profissional",
                descricao="Pra viação que já roda fretamento e frete além da linha regular, com mais frota e equipe.",
                preco_mensal=249.00,
                max_onibus=15,
                max_funcionarios=20,
                max_viagens_mes=400,
                modulo_passagens=True,
                modulo_fretamento=True,
                modulo_frete=True,
                modulo_frota=False,
                modulo_motorista=False,
                modulo_dre=False,
                modulo_white_label=False,
                modulo_nfse=False,
            )
        )
        print("Plano Profissional criado (R$ 249/mês)")

    if not db.query(Plano).filter(Plano.nome == "Completo").first():
        db.add(
            Plano(
                nome="Completo",
                descricao="Tudo liberado: gestão de frota, app do motorista, DRE, loja com a marca própria (white-label) e NFS-e, sem limite de ônibus, funcionários ou viagens.",
                preco_mensal=499.00,
                max_onibus=None,
                max_funcionarios=None,
                max_viagens_mes=None,
                modulo_passagens=True,
                modulo_fretamento=True,
                modulo_frete=True,
                modulo_frota=True,
                modulo_motorista=True,
                modulo_dre=True,
                modulo_white_label=True,
                modulo_nfse=True,
            )
        )
        print("Plano Completo criado (R$ 499/mês)")

    empresa = db.query(Empresa).filter(Empresa.cnpj == "00.000.000/0001-00").first()
    if not empresa:
        empresa = Empresa(nome="Viação Demo", cnpj="00.000.000/0001-00", email_contato="contato@viacaodemo.com")
        db.add(empresa)
        db.flush()
        print("Empresa demo criada: Viação Demo")

    if not db.query(Usuario).filter(Usuario.email == "admin@viacaodemo.com").first():
        admin = Usuario(
            tenant_id=empresa.id,
            nome="Admin Viação Demo",
            email="admin@viacaodemo.com",
            senha_hash=hash_senha("admin123"),
            role=UserRole.ADMIN_EMPRESA,
        )
        db.add(admin)
        print("Admin da empresa criado: admin@viacaodemo.com / admin123")

    if not db.query(Usuario).filter(Usuario.email == "atendente@viacaodemo.com").first():
        funcionario = Usuario(
            tenant_id=empresa.id,
            nome="Atendente Demo",
            email="atendente@viacaodemo.com",
            senha_hash=hash_senha("atendente123"),
            role=UserRole.FUNCIONARIO,
        )
        db.add(funcionario)
        print("Funcionário criado: atendente@viacaodemo.com / atendente123")

    onibus = db.query(Onibus).filter(Onibus.tenant_id == empresa.id).first()
    if not onibus:
        onibus = Onibus(tenant_id=empresa.id, identificacao="ABC-1234", tipo=TipoOnibus.EXECUTIVO)
        db.add(onibus)
        db.flush()
        numero = 1
        for fileira in range(1, 11):
            for coluna in range(1, 5):
                db.add(PoltronaOnibus(onibus_id=onibus.id, numero=str(numero), andar=1, fileira=fileira, coluna=coluna))
                numero += 1
        print("Ônibus demo criado com 40 poltronas")

    rota = db.query(Rota).filter(Rota.tenant_id == empresa.id).first()
    if not rota:
        rota = Rota(tenant_id=empresa.id, origem="São Paulo", destino="Rio de Janeiro")
        db.add(rota)
        db.flush()
        # Rota com parada intermediária, para exercitar venda por trecho.
        db.add(Parada(rota_id=rota.id, nome="São Paulo", ordem=0, peso_proximo=2))
        db.add(Parada(rota_id=rota.id, nome="Volta Redonda", ordem=1, peso_proximo=1))
        db.add(Parada(rota_id=rota.id, nome="Rio de Janeiro", ordem=2, peso_proximo=None))
        print("Rota demo criada: São Paulo -> Volta Redonda -> Rio de Janeiro")

    db.flush()
    if not db.query(Viagem).filter(Viagem.tenant_id == empresa.id).first():
        partida = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=1)
        viagem = Viagem(tenant_id=empresa.id, rota_id=rota.id, onibus_id=onibus.id, data_hora_partida=partida, preco=150.00)
        db.add(viagem)
        db.flush()
        for p in db.query(PoltronaOnibus).filter(PoltronaOnibus.onibus_id == onibus.id).all():
            db.add(PoltronaViagem(viagem_id=viagem.id, poltrona_onibus_id=p.id))
        print("Viagem demo criada para amanhã às 08:00")

    db.commit()
    print("\nSeed concluído com sucesso.")
finally:
    db.close()
