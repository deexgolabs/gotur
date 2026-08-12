"""Roda tudo que precisa acontecer uma vez por dia: backup do banco +
cobrança recorrente (gerar fatura de quem venceu o ciclo + atualizar
inadimplência/suspensão) + alerta de documento da frota vencendo.

Existe porque o plano gratuito do PythonAnywhere só dá 1 tarefa agendada
— então, em vez de precisar de dois slots (um pra backup_db.py, outro pra
gerar_faturas_mensais.py), esse script chama os dois em sequência e você
só precisa de UMA tarefa agendada apontando pra ele.

Se você estiver num plano do PythonAnywhere com mais slots (ou rodando
fora do PythonAnywhere), pode preferir agendar backup_db.py e
gerar_faturas_mensais.py separados — os dois continuam funcionando sozinhos.

Uso:
    python scripts/tarefas_diarias.py
    python scripts/tarefas_diarias.py --base-url https://minhaviacao.pythonanywhere.com
"""

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from scripts.backup_db import fazer_backup  # noqa: E402
from scripts.gerar_faturas_mensais import rodar as rodar_faturamento  # noqa: E402
from scripts.verificar_vencimentos import rodar as rodar_verificacao_vencimentos  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manter-backups", type=int, default=14, help="Quantos backups recentes manter (padrão: 14)")
    parser.add_argument(
        "--base-url",
        default="https://gotur.pythonanywhere.com",
        help="URL base do site em produção, usada no link de pagamento enviado por e-mail/WhatsApp",
    )
    parser.add_argument(
        "--dias-alerta-frota", type=int, default=15, help="Quantos dias de antecedência pra alertar documento da frota vencendo (padrão: 15)"
    )
    args = parser.parse_args()

    print("=== Backup do banco ===")
    fazer_backup(manter=args.manter_backups)

    print("\n=== Cobrança recorrente ===")
    rodar_faturamento(args.base_url)

    print("\n=== Documentos da frota vencendo ===")
    rodar_verificacao_vencimentos(args.dias_alerta_frota)
