"""Gera um par de chaves VAPID pra ativar o push notification real (Web
Push) — ver app/services/push_service.py. Rode uma vez, cole as duas linhas
no seu .env (ou nas variáveis de ambiente do PythonAnywhere) e reinicie a
aplicação.

Uso:
    backend/venv/Scripts/python.exe backend/scripts/gerar_chaves_vapid.py
"""

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid02
from py_vapid.utils import b64urlencode


def main() -> None:
    vapid = Vapid02()
    vapid.generate_keys()

    chave_privada = b64urlencode(vapid.private_key.private_numbers().private_value.to_bytes(32, "big"))
    chave_publica = b64urlencode(
        vapid.public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
    )

    print("Adicione isso ao seu .env (ou variáveis de ambiente):\n")
    print(f"GOTUR_VAPID_PUBLIC_KEY={chave_publica}")
    print(f"GOTUR_VAPID_PRIVATE_KEY={chave_privada}")
    print("GOTUR_VAPID_CLAIMS_EMAIL=seuemail@suaempresa.com")


if __name__ == "__main__":
    main()
