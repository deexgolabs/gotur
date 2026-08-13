from sqlalchemy import Integer, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import ModoCobranca


class ConfiguracaoPlataforma(Base):
    """Linha única (singleton) com a configuração de cobrança da PRÓPRIA
    plataforma GoTur — como o super admin cobra as empresas clientes pela
    assinatura (fatura mensal), não como cada empresa cobra os próprios
    clientes (isso é por tenant, ver Empresa.mercadopago_access_token /
    Empresa.modo_cobranca). Sempre há no máximo uma linha nessa tabela."""

    __tablename__ = "configuracao_plataforma"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mercadopago_access_token: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mercadopago_public_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    modo_cobranca: Mapped[ModoCobranca] = mapped_column(SAEnum(ModoCobranca), default=ModoCobranca.AUTOMATICA, nullable=False)

    # Taxa por transação (split), OPCIONAL — desligada por padrão (None/0).
    # Só desconta de verdade (via `application_fee` do Mercado Pago) se a
    # conta da empresa estiver conectada como sub-conta via OAuth
    # marketplace; com Access Token colado manualmente (o modelo usado
    # hoje), o Mercado Pago tende a ignorar/recusar esse parâmetro — ver
    # app/services/pagamento_provider.py.
    taxa_transacao_percentual: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    @property
    def mercadopago_configurado(self) -> bool:
        return bool(self.mercadopago_access_token)
