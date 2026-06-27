"""
Definições e handlers dos comandos de controle.

Cada CommandAction recebe o contexto do sistema (injetor, captura, histórico)
e executa sua ação. Essa separação permite testar cada handler isoladamente.
"""

import subprocess
import sys
from enum import Enum, auto
from typing import Callable, NamedTuple, Optional


class CommandType(Enum):
    DICTATION = auto()    # Texto a ser injetado literalmente
    CANCELA = auto()      # Descarta a gravação atual
    INTERROMPE = auto()   # Envia Ctrl+C para janela ativa
    REPETE = auto()       # Reenvia último comando
    LIMPA_TELA = auto()   # Envia "clear" ou Ctrl+L
    PARA = auto()         # Alias de CANCELA (compatibilidade semântica)


class ControlCommand(NamedTuple):
    type: CommandType
    raw_text: str


def handle_cancela(ctx: dict) -> str:
    """Descarta a gravação atual sem enviar nada."""
    return "Comando cancelado."


def handle_interrompe(ctx: dict) -> str:
    """
    Envia Ctrl+C para a janela ativa.

    No Linux: usa xdotool para simular Ctrl+C na janela em foco.
    No Windows: usa pyautogui.hotkey('ctrl', 'c').
    """
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "c")
        return "Ctrl+C enviado."
    except Exception as exc:
        return f"Falha ao enviar Ctrl+C: {exc}"


def handle_repete(ctx: dict) -> Optional[str]:
    """Reenvia o último texto transcrito."""
    last = ctx.get("last_dictation")
    if not last:
        return "Nenhum comando anterior para repetir."
    injector = ctx.get("injector")
    if injector:
        injector.inject(last)
    return f"Repetindo: {last!r}"


def handle_limpa_tela(ctx: dict) -> str:
    """Injeta 'clear' + Enter no terminal ativo."""
    injector = ctx.get("injector")
    if injector:
        injector.inject("clear", auto_enter=True)
    return "Tela limpa."


def handle_para(ctx: dict) -> str:
    """Alias semântico de cancela."""
    return handle_cancela(ctx)


# Mapa de tipo → handler
HANDLERS: dict[CommandType, Callable[[dict], Optional[str]]] = {
    CommandType.CANCELA: handle_cancela,
    CommandType.INTERROMPE: handle_interrompe,
    CommandType.REPETE: handle_repete,
    CommandType.LIMPA_TELA: handle_limpa_tela,
    CommandType.PARA: handle_para,
}
