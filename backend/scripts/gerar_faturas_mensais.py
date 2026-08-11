"""Cobrança recorrente: gera a fatura mensal de cada empresa (quando o
ciclo dela vence) e atualiza quem ficou inadimplente/suspenso por atraso.

Antes disso, o super admin tinha que entrar no painel e gerar cada fatura
na mão — isso fecha o ciclo sozinho. Ver app/services/faturamento.py pra
entender a regra do ciclo de 30 dias e o período de trial.

Pensado pra rodar uma vez por dia via tarefa agendada (ex: "Scheduled
Tasks" do PythonAnywhere) — ver DEPLOY.md.

Uso:
    python scripts/gerar_faturas_mensais.py
    python scripts/gerar_faturas_mensais.py --base-url https://minhaviacao.pythonanywhere.com
"""

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.services.assinatura import atualizar_situacao_assinaturas  # noqa: E402
from app.services.faturamento import gerar_faturas_do_dia  # noqa: E402


def rodar(base_url: str) -> None:
    db = SessionLocal()
    try:
        faturas = gerar_faturas_do_dia(db, base_url=base_url)
        for fatura in faturas:
            print(f"Fatura #{fatura.id} gerada — empresa {fatura.empresa_id}, R$ {fatura.valor}, vence {fatura.vencimento}")
        print(f"{len(faturas)} fatura(s) gerada(s).")

        atualizar_situacao_assinaturas(db)
        print("Situação de assinaturas atualizada (inadimplência/suspensão por atraso).")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default="https://gotur.pythonanywhere.com",
        help="URL base do site em produção, usada no link de pagamento enviado por e-mail/WhatsApp",
    )
    args = parser.parse_args()
    rodar(args.base_url)
