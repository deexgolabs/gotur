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

    # Nota fiscal de serviço eletrônica (NFS-e, ver app/services/nfse_provider.py).
    # Não existe uma API nacional única (cada prefeitura tem seu próprio
    # webservice) — o caminho realista é um agregador (Focus NFe, NFE.io,
    # PlugNotas etc). Sem essas duas variáveis configuradas, a emissão fica
    # apenas logada (terreno pronto, não implementado de verdade).
    nfse_provider_url: str | None = None
    nfse_provider_token: str | None = None

    # WhatsApp via Evolution API (self-hosted, ver
    # app/services/whatsapp_service.py). Sem isso configurado, o envio é
    # apenas logado (no-op) — não bloqueia a venda. `evolution_instance` é
    # o nome da instância/número conectado no seu servidor Evolution.
    evolution_api_url: str | None = None
    evolution_api_key: str | None = None
    evolution_instance: str | None = None

    # White-label: logos enviados pelas empresas (ver app/routers/empresas.py
    # e app/routers/loja.py). Fica fora do controle de versão.
    media_dir: str = str(BACKEND_DIR / "media")

    # Monitoramento de erro (opcional). Sem GOTUR_SENTRY_DSN configurado,
    # nada é enviado — crie uma conta grátis em sentry.io e cole o DSN do
    # projeto aqui para começar a receber erros de produção automaticamente.
    sentry_dsn: str | None = None

    # Push notification real (Web Push), ver app/services/push_service.py.
    # Sem as chaves VAPID configuradas, o envio é apenas logado (no-op) — não
    # bloqueia a mudança de status. Gere o par de chaves com:
    #   backend/venv/Scripts/python.exe backend/scripts/gerar_chaves_vapid.py
    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    vapid_claims_email: str = "naoresponda@gotur.com"

    # Cobrança recorrente (ver app/services/faturamento.py e
    # scripts/gerar_faturas_mensais.py). Empresa nova fica `trial` sem
    # cobrança até esses dias passarem desde o cadastro; depois disso o
    # ciclo é sempre de 30 em 30 dias a partir do vencimento da fatura
    # anterior.
    trial_dias_gratis: int = 14

    @property
    def cors_origins_list(self) -> list[str]:
        return [origem.strip() for origem in self.cors_origins.split(",") if origem.strip()]


settings = Settings()

if not settings.debug and settings.jwt_secret == "dev-secret-troque-em-producao":
    logger.warning(
        "GOTUR_JWT_SECRET não foi configurado em produção (GOTUR_DEBUG=false). "
        "Defina uma chave secreta forte antes de expor este servidor publicamente."
    )
