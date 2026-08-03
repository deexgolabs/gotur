"""Adaptador para hospedar a API GoTur (ASGI/FastAPI) no PythonAnywhere,
que serve aplicações via WSGI (mod_wsgi).

No editor de "WSGI configuration file" do PythonAnywhere (aba Web), apague o
conteúdo padrão e cole o snippet do DEPLOY.md que importa `application`
deste módulo.
"""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from app.main import app as _fastapi_app  # noqa: E402
from app.wsgi_adapter import ASGIParaWSGI  # noqa: E402

application = ASGIParaWSGI(_fastapi_app)
