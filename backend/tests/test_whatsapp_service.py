from datetime import datetime
from unittest.mock import MagicMock, patch

from app.config import settings
from app.services.whatsapp_service import _normalizar_numero, enviar_confirmacao_compra_whatsapp


def test_normalizar_numero_adiciona_ddi_brasil_quando_ausente():
    assert _normalizar_numero("(63) 99999-8888") == "5563999998888"


def test_normalizar_numero_mantem_ddi_ja_presente():
    assert _normalizar_numero("+55 63 99999-8888") == "5563999998888"


def test_sem_telefone_nao_faz_nada(monkeypatch):
    monkeypatch.setattr(settings, "evolution_api_url", "https://evolution.teste.com")
    monkeypatch.setattr(settings, "evolution_instance", "minha-instancia")
    with patch("app.services.whatsapp_service.urllib.request.urlopen") as mock_urlopen:
        enviar_confirmacao_compra_whatsapp(
            telefone=None,
            cliente_nome="Fulano",
            localizador="ABC123",
            origem="A",
            destino="B",
            data_hora_partida=datetime(2026, 1, 1, 10, 0),
            numero_poltrona="1",
        )
        mock_urlopen.assert_not_called()


def test_sem_evolution_configurada_nao_envia_http(monkeypatch):
    monkeypatch.setattr(settings, "evolution_api_url", None)
    monkeypatch.setattr(settings, "evolution_instance", None)
    with patch("app.services.whatsapp_service.urllib.request.urlopen") as mock_urlopen:
        enviar_confirmacao_compra_whatsapp(
            telefone="(63) 99999-8888",
            cliente_nome="Fulano",
            localizador="ABC123",
            origem="A",
            destino="B",
            data_hora_partida=datetime(2026, 1, 1, 10, 0),
            numero_poltrona="1",
        )
        mock_urlopen.assert_not_called()


def test_evolution_configurada_monta_requisicao_correta(monkeypatch):
    monkeypatch.setattr(settings, "evolution_api_url", "https://evolution.teste.com/")
    monkeypatch.setattr(settings, "evolution_api_key", "chave-secreta")
    monkeypatch.setattr(settings, "evolution_instance", "minha-instancia")

    with patch("app.services.whatsapp_service.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = MagicMock()
        enviar_confirmacao_compra_whatsapp(
            telefone="(63) 99999-8888",
            cliente_nome="Fulano",
            localizador="ABC123",
            origem="A",
            destino="B",
            data_hora_partida=datetime(2026, 1, 1, 10, 0),
            numero_poltrona="1",
        )
        mock_urlopen.assert_called_once()
        requisicao = mock_urlopen.call_args[0][0]
        assert requisicao.full_url == "https://evolution.teste.com/message/sendText/minha-instancia"
        assert requisicao.get_header("Apikey") == "chave-secreta"
        assert b'"number": "5563999998888"' in requisicao.data
        assert b"ABC123" in requisicao.data
