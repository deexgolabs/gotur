"""Alerta proativo: verifica documentos da frota (CRLV, seguro, revisão
preventiva) perto de vencer e notifica cada empresa por e-mail/WhatsApp —
fecha o ciclo que a tela de Manutenção de Frota começa (hoje o selo
"vencendo/vencido" só aparece se alguém abrir a tela de um ônibus).

Pensado pra rodar uma vez por dia via tarefa agendada, junto com as outras
(ver scripts/tarefas_diarias.py).

Uso:
    python scripts/verificar_vencimentos.py
    python scripts/verificar_vencimentos.py --dias 30
"""

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.services.manutencao import verificar_documentos_vencendo  # noqa: E402


def rodar(dias_alerta: int = 15) -> None:
    db = SessionLocal()
    try:
        total = verificar_documentos_vencendo(db, dias_alerta=dias_alerta)
        print(f"{total} empresa(s) notificada(s) sobre documentos da frota vencendo.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dias", type=int, default=15, help="Quantos dias de antecedência pra alertar (padrão: 15)")
    args = parser.parse_args()
    rodar(args.dias)
