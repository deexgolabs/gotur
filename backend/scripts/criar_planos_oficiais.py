"""Cria os 3 planos oficiais da plataforma (Essencial/Profissional/Completo)
se ainda não existirem — idempotente, seguro de rodar mais de uma vez e em
produção (ao contrário de seed.py, não cria empresa/usuário de demonstração).

Pacotes:
  Essencial (R$ 99/mês)      — só passagens, pra quem tá começando.
  Profissional (R$ 249/mês)  — passagens + fretamento + frete + eventos +
                                academia: todos os módulos que geram
                                receita direta, sem as ferramentas de
                                back-office abaixo.
  Completo (R$ 499/mês)      — tudo liberado: frota, motoristas, DRE,
                                white-label, NFS-e, sem limite de ônibus/
                                funcionários/viagens.

Se um plano com o mesmo nome já existir, ele NÃO é alterado — o objetivo
aqui é só garantir que os 3 existam. Pra corrigir os módulos de um plano
que já existe (ex: ele foi criado antes de eventos/academia existirem e
ficou com os módulos errados), use a tela Planos no painel do super admin.

Uso:
    python scripts/criar_planos_oficiais.py
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.models.plano import Plano  # noqa: E402

PLANOS = [
    dict(
        nome="Essencial",
        descricao="Pra quem tá começando a vender passagem online: controle de poltrona e venda, sem os módulos extras.",
        preco_mensal=99.00,
        max_onibus=3,
        max_funcionarios=5,
        max_viagens_mes=60,
        modulo_passagens=True,
        modulo_fretamento=False,
        modulo_frete=False,
        modulo_eventos=False,
        modulo_academia=False,
        modulo_frota=False,
        modulo_motorista=False,
        modulo_dre=False,
        modulo_white_label=False,
        modulo_nfse=False,
    ),
    dict(
        nome="Profissional",
        descricao="Todos os módulos que geram venda — passagem, fretamento, frete, eventos e academia —, com mais frota e equipe.",
        preco_mensal=249.00,
        max_onibus=15,
        max_funcionarios=20,
        max_viagens_mes=400,
        modulo_passagens=True,
        modulo_fretamento=True,
        modulo_frete=True,
        modulo_eventos=True,
        modulo_academia=True,
        modulo_frota=False,
        modulo_motorista=False,
        modulo_dre=False,
        modulo_white_label=False,
        modulo_nfse=False,
    ),
    dict(
        nome="Completo",
        descricao="Tudo liberado: gestão de frota, app do motorista, DRE, loja com a marca própria (white-label) e NFS-e, sem limite de ônibus, funcionários ou viagens.",
        preco_mensal=499.00,
        max_onibus=None,
        max_funcionarios=None,
        max_viagens_mes=None,
        modulo_passagens=True,
        modulo_fretamento=True,
        modulo_frete=True,
        modulo_eventos=True,
        modulo_academia=True,
        modulo_frota=True,
        modulo_motorista=True,
        modulo_dre=True,
        modulo_white_label=True,
        modulo_nfse=True,
    ),
]


def rodar() -> None:
    db = SessionLocal()
    try:
        criados = 0
        for dados in PLANOS:
            if db.query(Plano).filter(Plano.nome == dados["nome"]).first():
                print(f"Plano {dados['nome']} já existe — pulando.")
                continue
            db.add(Plano(**dados))
            criados += 1
            print(f"Plano {dados['nome']} criado (R$ {dados['preco_mensal']:.2f}/mês).")
        db.commit()
        print(f"\nConcluído: {criados} plano(s) criado(s).")
    finally:
        db.close()


if __name__ == "__main__":
    rodar()
