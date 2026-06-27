"""
Detecta se a janela ativa é um terminal válido antes de injetar texto.

Estratégia por plataforma:
- Linux/X11: xdotool getactivewindow getwindowname
- Linux/Wayland: xdg-open não funciona; fallback via /proc/{pid}/cmdline da janela ativa
- Windows: win32gui.GetWindowText(win32gui.GetForegroundWindow())
- macOS: AppleScript (não suportado nesta versão)
"""

import platform
import subprocess
from typing import Optional

from logging_setup import get_logger

logger = get_logger(__name__)


def get_active_window_name() -> Optional[str]:
    """Retorna o título da janela ativa ou None em caso de falha."""
    system = platform.system()

    if system == "Linux":
        # Tenta X11 primeiro
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback: wmctrl
        try:
            result = subprocess.run(
                ["wmctrl", "-a", ":ACTIVE:"],
                capture_output=True, text=True, timeout=2,
            )
        except FileNotFoundError:
            pass

        logger.warning(
            "Não foi possível obter janela ativa. "
            "Instale xdotool: sudo apt install xdotool"
        )
        return None

    elif system == "Windows":
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value
        except Exception as exc:
            logger.warning("Falha ao obter janela ativa no Windows: %s", exc)
            return None

    return None


def is_terminal_window(window_name: Optional[str], valid_terminals: list[str]) -> bool:
    """
    Verifica se o nome da janela corresponde a um terminal conhecido.

    Retorna True (permissivo) se não conseguir detectar a janela,
    pois é melhor injetar do que silenciar o usuário.
    """
    if window_name is None:
        logger.warning(
            "Janela ativa não detectada — permitindo injeção (modo permissivo)."
        )
        return True  # fail-open: não bloquear se não conseguir detectar

    window_lower = window_name.lower()
    for term in valid_terminals:
        if term.lower() in window_lower:
            logger.debug("Janela '%s' reconhecida como terminal ('%s').", window_name, term)
            return True

    logger.warning(
        "Janela ativa '%s' não reconhecida como terminal. "
        "Injeção de texto bloqueada. Adicione o nome em 'injection.valid_terminals' no config.",
        window_name,
    )
    return False
