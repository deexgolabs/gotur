"""Academia: mantém a janela de ocorrências de turma sempre 8 semanas à
frente, gera a mensalidade de quem venceu o ciclo, e atualiza quem ficou
inadimplente/suspenso por atraso. Ver app/services/ocorrencias_turma.py,
app/services/faturamento_matricula.py e app/services/matricula_status.py.

Pensado pra rodar uma vez por dia — não tem tarefa agendada própria, é
chamado por scripts/tarefas_diarias.py junto com backup + cobrança da
assinatura da plataforma + alerta de vencimento de frota, porque o plano
gratuito do PythonAnywhere só dá 1 tarefa agendada (ver DEPLOY.md).

Uso:
    python scripts/gerar_faturas_matricula.py
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.services.faturamento_matricula import gerar_faturas_matricula_do_dia  # noqa: E402
from app.services.matricula_status import atualizar_situacao_matriculas  # noqa: E402
from app.services.ocorrencias_turma import estender_janela_todas_turmas  # noqa: E402


def rodar() -> None:
    db = SessionLocal()
    try:
        total_ocorrencias = estender_janela_todas_turmas(db)
        print(f"{total_ocorrencias} ocorrência(s) de turma gerada(s).")

        faturas = gerar_faturas_matricula_do_dia(db)
        for fatura in faturas:
            print(f"Fatura de matrícula #{fatura.id} gerada — matrícula {fatura.matricula_id}, R$ {fatura.valor}, vence {fatura.vencimento}")
        print(f"{len(faturas)} fatura(s) de matrícula gerada(s).")

        atualizar_situacao_matriculas(db)
        print("Situação de matrículas atualizada (inadimplência/suspensão por atraso).")
    finally:
        db.close()


if __name__ == "__main__":
    rodar()
