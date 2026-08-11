"""Backup do banco SQLite, com rotação (mantém as N cópias mais recentes).

Feito pra rodar como uma tarefa agendada (ex: "Scheduled Tasks" do
PythonAnywhere, uma vez por dia). Só cuida de SQLite — se GOTUR_DATABASE_URL
apontar pra Postgres/MySQL em produção, use a ferramenta de backup do
próprio provedor (pg_dump, mysqldump, ou o backup automático do serviço
gerenciado) em vez deste script.

Uso:
    python scripts/backup_db.py
    python scripts/backup_db.py --manter 30
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402

BACKUPS_DIR = BACKEND_DIR / "backups"


def _caminho_db_sqlite() -> Path | None:
    url = settings.database_url
    if not url.startswith("sqlite:///"):
        return None
    return Path(url.removeprefix("sqlite:///"))


def fazer_backup(manter: int = 14) -> Path | None:
    origem = _caminho_db_sqlite()
    if origem is None:
        print(f"GOTUR_DATABASE_URL não é SQLite ({settings.database_url}); use o backup do provedor do banco.")
        return None
    if not origem.exists():
        print(f"Banco não encontrado em {origem}")
        return None

    BACKUPS_DIR.mkdir(exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = BACKUPS_DIR / f"gotur_{carimbo}.db"
    shutil.copy2(origem, destino)
    print(f"Backup salvo em {destino}")

    backups = sorted(BACKUPS_DIR.glob("gotur_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for antigo in backups[manter:]:
        antigo.unlink()
        print(f"Removido backup antigo: {antigo.name}")

    return destino


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manter", type=int, default=14, help="Quantas cópias recentes manter (padrão: 14)")
    args = parser.parse_args()
    fazer_backup(manter=args.manter)
