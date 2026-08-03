import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sqlalchemy import inspect, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from app import models  # noqa: F401 - garante que os modelos sejam registrados no metadata
from app.config import settings
from app.database import Base, engine
from app.routers import auth, checkin, empresas, onibus, passagens, poltronas, relatorios, rotas, usuarios, viagens

Base.metadata.create_all(bind=engine)


def _aplicar_migracoes_leves() -> None:
    """Sem Alembic ainda: adiciona colunas novas em bancos sqlite já existentes."""
    inspecao = inspect(engine)
    if "passagens" not in inspecao.get_table_names():
        return
    colunas = {c["name"] for c in inspecao.get_columns("passagens")}
    if "checkin_em" not in colunas:
        with engine.begin() as conexao:
            conexao.execute(text("ALTER TABLE passagens ADD COLUMN checkin_em DATETIME"))


_aplicar_migracoes_leves()

app = FastAPI(title="GoTur API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = FastAPI(title="GoTur API - v1")
for router in (
    auth.router,
    empresas.router,
    usuarios.router,
    onibus.router,
    rotas.router,
    viagens.router,
    poltronas.router,
    passagens.router,
    passagens.meu_router,
    relatorios.router,
    checkin.router,
):
    api.include_router(router)

app.mount("/api", api)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
