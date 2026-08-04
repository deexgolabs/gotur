import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DB_PATH = BACKEND_DIR / "test_gotur.db"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ["GOTUR_DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["GOTUR_JWT_SECRET"] = "test-secret-nao-usar-em-producao"
os.environ["GOTUR_DEBUG"] = "true"

sys.path.insert(0, str(BACKEND_DIR))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402,F401
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

Base.metadata.create_all(bind=engine)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _limpar_banco_entre_testes():
    """Cada teste começa com o banco vazio (tabelas mantidas, dados apagados)."""
    yield
    session = SessionLocal()
    try:
        for tabela in reversed(Base.metadata.sorted_tables):
            session.execute(tabela.delete())
        session.commit()
    finally:
        session.close()
