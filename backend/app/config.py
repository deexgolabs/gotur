import logging
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
logger = logging.getLogger("gotur.config")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GOTUR_", env_file=str(BACKEND_DIR / ".env"), extra="ignore")

    app_name: str = "GoTur API"
    debug: bool = True

    # Por padrão usa um sqlite local ao lado do código. Em produção, defina
    # GOTUR_DATABASE_URL (ex: postgresql://usuario:senha@host/banco).
    database_url: str = f"sqlite:///{BACKEND_DIR / 'gotur.db'}"

    jwt_secret: str = "dev-secret-troque-em-producao"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8
    seat_hold_minutes: int = 5

    # Domínios autorizados a chamar a API separados por vírgula (ex:
    # "https://minhaviacao.com,https://app.minhaviacao.com"). "*" libera geral
    # — ok para o front que é servido pelo próprio backend, mas deve ser
    # restringido se outro domínio for consumir a API.
    cors_origins: str = "*"

    # E-mail (Fase 5): opcional. Se smtp_host não for configurado, o envio é
    # apenas logado (no-op) — não bloqueia a venda.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_remetente: str = "naoresponda@gotur.com"

    # Gateway de pagamento (Fase 5, ver app/services/pagamento_provider.py).
    # Sem GOTUR_GATEWAY_API_KEY definido, roda em modo simulado: Pix gera um
    # código copia-e-cola de mentira e fica pendente até alguém confirmar
    # (tela "já paguei" ou o endpoint de confirmação simulada) — é o
    # comportamento de um gateway real (Mercado Pago, Stripe, Asaas etc.)
    # sem precisar de conta/chave real. Configurando a chave, a cobrança
    # passa a ser feita de verdade via MercadoPagoProvider.
    gateway_api_key: str | None = None
    pix_expiracao_minutos: int = 15

    # WhatsApp (Fase 5, ver app/services/whatsapp_service.py). Sem isso
    # configurado, o envio é apenas logado (no-op) — não bloqueia a venda.
    # Pensado para uma API HTTP simples (Z-API, Meta Cloud API, etc): um
    # POST para `whatsapp_api_url` com o token de autenticação.
    whatsapp_api_url: str | None = None
    whatsapp_api_token: str | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        return [origem.strip() for origem in self.cors_origins.split(",") if origem.strip()]


settings = Settings()

if not settings.debug and settings.jwt_secret == "dev-secret-troque-em-producao":
    logger.warning(
        "GOTUR_JWT_SECRET não foi configurado em produção (GOTUR_DEBUG=false). "
        "Defina uma chave secreta forte antes de expor este servidor publicamente."
    )
