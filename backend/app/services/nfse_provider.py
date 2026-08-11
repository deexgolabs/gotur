"""Nota fiscal de serviço eletrônica (NFS-e) — terreno pronto para
integração, ainda não implementado de verdade.

Diferente de gateway de pagamento (onde o Mercado Pago cobre o Brasil
inteiro com uma API só), NFS-e não tem uma API nacional única: cada
prefeitura mantém seu próprio webservice, com layout e regras próprias. O
caminho realista pra maioria das viações é contratar um agregador que fala
com as prefeituras por você — os mais usados no mercado são:

- Focus NFe (https://focusnfe.com.br) — API REST simples, boa documentação.
- NFE.io (https://nfe.io)
- PlugNotas (https://plugnotas.com.br)

Pra ativar de verdade:
1. Contrate um desses (ou outro agregador) e pegue a URL base + token da API.
2. Configure GOTUR_NFSE_PROVIDER_URL e GOTUR_NFSE_PROVIDER_TOKEN.
3. Implemente `NfseProviderReal.emitir()` chamando o endpoint de emissão do
   agregador escolhido (o formato do payload varia por provedor — consulte
   a documentação de quem for contratado).
4. Nenhum outro ponto do sistema precisa mudar — `obter_nfse_provider()` já
   troca automaticamente pro provider real.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger("gotur.nfse")


@dataclass
class ResultadoNfse:
    numero: str | None
    status: str  # "emitida" | "simulada" | "erro"
    url_pdf: str | None = None
    chave_acesso: str | None = None


class NfseProvider(ABC):
    @abstractmethod
    def emitir(self, *, referencia: str, valor: float, cliente_nome: str, cliente_documento: str, descricao: str) -> ResultadoNfse:
        ...


class NfseSimuladaProvider(NfseProvider):
    """Provider padrão quando nenhum agregador está configurado — só
    registra no log, não emite nada de verdade. Deixa o resto do sistema
    (botão "Emitir NFS-e", auditoria) já funcionando, esperando só a
    integração real ser plugada."""

    def emitir(self, *, referencia: str, valor: float, cliente_nome: str, cliente_documento: str, descricao: str) -> ResultadoNfse:
        logger.info(
            "[NFS-e não emitida - agregador não configurado] %s: R$ %.2f para %s (%s)",
            referencia,
            valor,
            cliente_nome,
            cliente_documento,
        )
        return ResultadoNfse(numero=None, status="simulada")


class NfseProviderReal(NfseProvider):
    """Esqueleto pronto — implemente `emitir()` chamando a API do agregador
    escolhido (ver docstring do módulo) antes de configurar
    GOTUR_NFSE_PROVIDER_URL/GOTUR_NFSE_PROVIDER_TOKEN em produção."""

    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token

    def emitir(self, *, referencia: str, valor: float, cliente_nome: str, cliente_documento: str, descricao: str) -> ResultadoNfse:
        raise NotImplementedError(
            "Integração com agregador de NFS-e ainda não implementada. "
            "Implemente NfseProviderReal.emitir() antes de configurar GOTUR_NFSE_PROVIDER_URL/TOKEN."
        )


def obter_nfse_provider() -> NfseProvider:
    if settings.nfse_provider_url and settings.nfse_provider_token:
        return NfseProviderReal(settings.nfse_provider_url, settings.nfse_provider_token)
    return NfseSimuladaProvider()


def nfse_configurada() -> bool:
    return bool(settings.nfse_provider_url and settings.nfse_provider_token)
