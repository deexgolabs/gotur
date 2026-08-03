"""Adaptador ASGI -> WSGI mínimo, para hospedar a API (FastAPI/ASGI) em
servidores que só falam WSGI, como o uWSGI do PythonAnywhere.

Usamos um adaptador próprio (em vez do pacote `a2wsgi`) porque a estratégia
dele de rodar o event loop numa thread separada trava (deadlock) dentro do
modelo de processo do uWSGI do PythonAnywhere. Este adaptador roda um
`asyncio` event loop novo por requisição, na mesma thread que o uWSGI já
está usando — sem threads extras e sem `asyncio.run()` (que tenta registrar
signal handlers, o que também conflita com o uWSGI).

Suficiente para uma API REST + arquivos estáticos (sem streaming/websocket).
"""

import asyncio
from http import HTTPStatus
from urllib.parse import unquote


def _montar_scope(environ: dict) -> dict:
    headers = []
    for chave, valor in environ.items():
        if chave.startswith("HTTP_"):
            nome = chave[5:].replace("_", "-").lower().encode("latin-1")
            headers.append((nome, valor.encode("latin-1")))
    if environ.get("CONTENT_TYPE"):
        headers.append((b"content-type", environ["CONTENT_TYPE"].encode("latin-1")))
    if environ.get("CONTENT_LENGTH"):
        headers.append((b"content-length", environ["CONTENT_LENGTH"].encode("latin-1")))

    path = unquote(environ.get("PATH_INFO", ""))
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": environ["REQUEST_METHOD"],
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": environ.get("QUERY_STRING", "").encode("latin-1"),
        "headers": headers,
        "server": (environ.get("SERVER_NAME", ""), int(environ.get("SERVER_PORT") or 0)),
        "client": (environ.get("REMOTE_ADDR", ""), 0),
        "scheme": environ.get("wsgi.url_scheme", "http"),
    }


class ASGIParaWSGI:
    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    def __call__(self, environ, start_response):
        scope = _montar_scope(environ)
        corpo_requisicao = environ["wsgi.input"].read()
        corpo_ja_enviado = False

        async def receive():
            nonlocal corpo_ja_enviado
            if not corpo_ja_enviado:
                corpo_ja_enviado = True
                return {"type": "http.request", "body": corpo_requisicao, "more_body": False}
            return {"type": "http.disconnect"}

        resposta = {"status": 500, "headers": [], "corpo": bytearray()}

        async def send(mensagem):
            if mensagem["type"] == "http.response.start":
                resposta["status"] = mensagem["status"]
                resposta["headers"] = mensagem.get("headers", [])
            elif mensagem["type"] == "http.response.body":
                resposta["corpo"] += mensagem.get("body", b"")

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.asgi_app(scope, receive, send))
        finally:
            loop.close()

        try:
            frase = HTTPStatus(resposta["status"]).phrase
        except ValueError:
            frase = ""
        status_line = f"{resposta['status']} {frase}".strip()
        headers = [(chave.decode("latin-1"), valor.decode("latin-1")) for chave, valor in resposta["headers"]]
        start_response(status_line, headers)
        return [bytes(resposta["corpo"])]
