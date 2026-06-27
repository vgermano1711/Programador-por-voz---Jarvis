"""
Injeta texto transcrito na janela ativa do terminal.

Método padrão: clipboard (pyperclip + Ctrl+V).
Por que clipboard em vez de pyautogui.typewrite?
- typewrite digita char por char: lento para textos longos e quebra com
  caracteres especiais (acentos, símbolos).
- clipboard: copia tudo de uma vez e cola com Ctrl+V — instantâneo e
  suporta Unicode completo.
- Trade-off: polui o clipboard do usuário; aceitável para uso em terminal.

Fallback "type": usa pyautogui.write() para ambientes onde clipboard não
funciona (ex: conexão SSH sem X forwarding).
"""

import time
from typing import Optional

from logging_setup import get_logger
from .terminal_validator import get_active_window_name, is_terminal_window

logger = get_logger(__name__)


class TextInjector:
    """
    Gerencia injeção de texto no terminal ativo.

    Uso:
        injector = TextInjector(cfg)
        injector.inject("print('hello world')")
    """

    def __init__(self, cfg) -> None:
        self._method: str = cfg.get("injection", "method", default="clipboard")
        self._auto_enter: bool = cfg.get("injection", "auto_enter", default=True)
        self._paste_delay: float = cfg.get("injection", "paste_delay_ms", default=100) / 1000
        self._valid_terminals: list[str] = cfg.get(
            "injection", "valid_terminals", default=[]
        )

    def inject(self, text: str, auto_enter: Optional[bool] = None) -> bool:
        """
        Injeta texto na janela ativa.

        Args:
            text: Texto a injetar.
            auto_enter: Sobrescreve config auto_enter se fornecido.

        Returns:
            True em sucesso, False em falha.
        """
        if not text:
            return False

        # Verifica se janela ativa é terminal
        window_name = get_active_window_name()
        if not is_terminal_window(window_name, self._valid_terminals):
            logger.warning(
                "Injeção bloqueada: janela '%s' não é um terminal reconhecido.", window_name
            )
            return False

        should_enter = auto_enter if auto_enter is not None else self._auto_enter

        try:
            if self._method == "clipboard":
                return self._inject_clipboard(text, should_enter)
            else:
                return self._inject_type(text, should_enter)
        except Exception as exc:
            logger.error("Falha na injeção de texto: %s", exc, exc_info=True)
            return False

    def _inject_clipboard(self, text: str, auto_enter: bool) -> bool:
        """Copia texto para clipboard e simula Ctrl+V."""
        try:
            import pyperclip
            import pyautogui

            # Salva clipboard anterior para restaurar depois (opcional)
            try:
                previous_clipboard = pyperclip.paste()
            except Exception:
                previous_clipboard = None

            pyperclip.copy(text)
            logger.debug("Texto copiado para clipboard: %r", text[:50])

            time.sleep(self._paste_delay)
            pyautogui.hotkey("ctrl", "v")
            logger.debug("Ctrl+V enviado.")

            if auto_enter:
                time.sleep(self._paste_delay)
                pyautogui.press("enter")
                logger.debug("Enter pressionado.")

            return True

        except ImportError as exc:
            logger.error(
                "Dependência não instalada: %s. Execute: pip install pyperclip pyautogui", exc
            )
            return False
        except Exception as exc:
            logger.error("Erro no método clipboard: %s", exc)
            return False

    def _inject_type(self, text: str, auto_enter: bool) -> bool:
        """Digita texto caractere por caractere (fallback para ambientes sem clipboard)."""
        try:
            import pyautogui

            # interval=0 é mais rápido mas pode perder chars; 0.01 é seguro
            pyautogui.write(text, interval=0.01)
            if auto_enter:
                pyautogui.press("enter")
            return True

        except Exception as exc:
            logger.error("Erro no método type: %s", exc)
            return False
