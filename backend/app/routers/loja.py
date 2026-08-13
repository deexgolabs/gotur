"""Rotas de página da loja white-label (/loja/{slug}) — servem HTML/JSON
direto no app principal (não no sub-app /api), por isso ficam registradas
manualmente em app/main.py, antes do mount estático do frontend."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.empresa import Empresa

router = APIRouter()

FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"
LOJA_SHELL = FRONTEND_DIR / "loja" / "index.html"
SERVICE_WORKER_SRC = FRONTEND_DIR / "service-worker.js"

COR_PADRAO = "#6E00A7"
ICONE_PADRAO_192 = "/icons/icon-192.png"
ICONE_PADRAO_512 = "/icons/icon-512.png"


def _buscar_empresa_por_slug(db: Session, slug: str) -> Empresa:
    empresa = db.query(Empresa).filter(Empresa.slug == slug, Empresa.ativo.is_(True)).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    return empresa


@router.get("/loja/{slug}", response_class=HTMLResponse)
def pagina_loja(slug: str, db: Session = Depends(get_db)):
    _buscar_empresa_por_slug(db, slug)
    if not LOJA_SHELL.exists():
        raise HTTPException(status_code=500, detail="Loja ainda não configurada no servidor")
    return HTMLResponse(LOJA_SHELL.read_text(encoding="utf-8"))


@router.get("/loja/{slug}/manifest.json")
def manifest_loja(slug: str, db: Session = Depends(get_db)):
    empresa = _buscar_empresa_por_slug(db, slug)
    cor = empresa.cor_primaria or COR_PADRAO
    if empresa.logo_filename:
        icone_192 = f"/media/empresas/{empresa.id}/icon-192.png?v={empresa.logo_filename}"
        icone_512 = f"/media/empresas/{empresa.id}/icon-512.png?v={empresa.logo_filename}"
    else:
        icone_192, icone_512 = ICONE_PADRAO_192, ICONE_PADRAO_512

    manifesto = {
        "id": f"/loja/{slug}",
        "name": empresa.nome,
        "short_name": empresa.nome[:30],
        "description": f"Compre passagens e acompanhe fretamentos de {empresa.nome}.",
        "start_url": f"/loja/{slug}",
        "scope": f"/loja/{slug}",
        "display": "standalone",
        "background_color": cor,
        "theme_color": cor,
        "orientation": "portrait-primary",
        "lang": "pt-BR",
        "icons": [
            {"src": icone_192, "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": icone_512, "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    }
    return JSONResponse(manifesto)


@router.get("/loja/{slug}/service-worker.js")
def service_worker_loja(slug: str, db: Session = Depends(get_db)):
    _buscar_empresa_por_slug(db, slug)
    return FileResponse(SERVICE_WORKER_SRC, media_type="application/javascript")
