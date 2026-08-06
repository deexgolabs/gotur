import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from app import models  # noqa: F401 - garante que os modelos sejam registrados no metadata
from app.config import settings
from app.routers import (
    auditoria,
    auth,
    checkin,
    empresas,
    faturas,
    onibus,
    passagens,
    planos,
    plataforma,
    poltronas,
    relatorios,
    rotas,
    usuarios,
    viagens,
)

# Schema do banco é gerenciado via Alembic (ver backend/alembic/), não mais
# criado/alterado automaticamente aqui. Rode `alembic upgrade head` antes de
# subir a aplicação (veja DEPLOY.md).

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
    auditoria.router,
    planos.router,
    faturas.router,
    plataforma.router,
):
    api.include_router(router)

app.mount("/api", api)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
