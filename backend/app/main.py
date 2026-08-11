import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from app import models  # noqa: F401 - garante que os modelos sejam registrados no metadata
from app.config import settings

if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1, environment="debug" if settings.debug else "production")
from app.routers import (
    auditoria,
    auth,
    avaliacoes,
    checkin,
    cupons,
    empresas,
    faturas,
    fretamentos,
    fretes,
    loja,
    onibus,
    passagens,
    pedidos_pagamento,
    planos,
    plataforma,
    poltronas,
    push,
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
    pedidos_pagamento.router,
    relatorios.router,
    checkin.router,
    auditoria.router,
    planos.router,
    faturas.router,
    plataforma.router,
    fretamentos.router,
    fretes.router,
    avaliacoes.router,
    push.router,
    cupons.router,
):
    api.include_router(router)

app.mount("/api", api)

MEDIA_DIR = Path(settings.media_dir)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

# Rotas de página da loja white-label (/loja/{slug}...) precisam ser
# registradas antes do mount estático abaixo, senão o StaticFiles (montado
# em "/") intercepta a requisição primeiro e devolve 404 genérico.
app.include_router(loja.router)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
