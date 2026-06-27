"""
Testes para o TextInjector com pyautogui e pyperclip mockados.

pyperclip e pyautogui são injetados em sys.modules antes de qualquer import,
pois o injector os importa dentro dos métodos (_inject_clipboard etc.).
Os mocks ficam disponíveis como atributos de MagicMock e podemos inspecioná-los.
"""

import sys
import pytest
from unittest.mock import patch, MagicMock, call

# Cria módulos mock globais antes de qualquer import do código de produção
_mock_pyperclip = MagicMock(name="pyperclip")
_mock_pyautogui = MagicMock(name="pyautogui")
sys.modules["pyperclip"] = _mock_pyperclip
sys.modules["pyautogui"] = _mock_pyautogui


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reinicia os mocks antes de cada teste para evitar interferência."""
    _mock_pyperclip.reset_mock()
    _mock_pyautogui.reset_mock()
    _mock_pyperclip.paste.return_value = ""


@pytest.fixture
def injector(cfg):
    cfg.set("clipboard", "injection", "method")
    cfg.set(True, "injection", "auto_enter")
    cfg.set(10, "injection", "paste_delay_ms")
    cfg.set(["terminal", "bash", "claude"], "injection", "valid_terminals")
    from text_injector import TextInjector
    return TextInjector(cfg)


class TestClipboardInjection:
    def test_injeta_texto_simples(self, injector):
        with patch("text_injector.injector.get_active_window_name",
                   return_value="terminal"):
            result = injector.inject("print('hello')")

        assert result is True
        _mock_pyperclip.copy.assert_called_once_with("print('hello')")
        _mock_pyautogui.hotkey.assert_called_once_with("ctrl", "v")
        _mock_pyautogui.press.assert_called_once_with("enter")

    def test_sem_auto_enter(self, cfg):
        cfg.set(False, "injection", "auto_enter")
        from text_injector import TextInjector
        injector = TextInjector(cfg)

        with patch("text_injector.injector.get_active_window_name",
                   return_value="terminal"):
            injector.inject("texto sem enter")

        _mock_pyautogui.press.assert_not_called()

    def test_texto_vazio_nao_injeta(self, injector):
        result = injector.inject("")
        assert result is False
        _mock_pyperclip.copy.assert_not_called()

    def test_texto_none_nao_injeta(self, injector):
        result = injector.inject(None)
        assert result is False


class TestTerminalValidation:
    def test_bloqueia_janela_nao_terminal(self, injector):
        with patch("text_injector.injector.get_active_window_name",
                   return_value="Firefox — Mozilla Firefox"):
            result = injector.inject("print('hello')")
        assert result is False
        _mock_pyperclip.copy.assert_not_called()

    def test_permite_janela_claude(self, injector):
        with patch("text_injector.injector.get_active_window_name",
                   return_value="claude — Terminal"):
            result = injector.inject("texto")
        assert result is True
        _mock_pyperclip.copy.assert_called_once_with("texto")

    def test_permite_quando_janela_nao_detectada(self, injector):
        with patch("text_injector.injector.get_active_window_name",
                   return_value=None):
            result = injector.inject("texto")
        # fail-open: sem janela detectada, permite injeção
        assert result is True


class TestTypeMethod:
    def test_injeta_por_typewrite(self, cfg):
        cfg.set("type", "injection", "method")
        cfg.set(["terminal"], "injection", "valid_terminals")
        from text_injector import TextInjector
        injector = TextInjector(cfg)

        with patch("text_injector.injector.get_active_window_name",
                   return_value="terminal"):
            result = injector.inject("hello")

        assert result is True
        _mock_pyautogui.write.assert_called_once_with("hello", interval=0.01)
        _mock_pyautogui.press.assert_called_once_with("enter")
