"""
Ícone na bandeja do sistema para feedback visual de status.

Estados:
  idle       — sistema ocioso, aguardando hotkey
  recording  — microfone ativo, capturando áudio
  processing — transcrevendo / interpretando
  error      — erro no pipeline

Usa pystray + Pillow para desenhar ícones programaticamente,
sem depender de arquivos .png externos (mais portável).

Trade-off de pystray: no Linux requer AppIndicator ou ayatana-appindicator.
Em ambientes headless/CI, desabilitar via ui.tray_enabled=false na config.
"""

import threading
from typing import Callable, Optional

from logging_setup import get_logger

logger = get_logger(__name__)

# Mapeamento de estado → cor do ícone
_STATUS_COLORS = {
    "idle": (100, 100, 100),        # Cinza
    "recording": (220, 50, 50),     # Vermelho
    "processing": (50, 150, 220),   # Azul
    "error": (255, 165, 0),         # Laranja
}


def _make_icon_image(color: tuple[int, int, int], size: int = 64):
    """Gera imagem PIL de círculo colorido para o ícone da bandeja."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(*color, 255),
    )
    return img


class TrayApp:
    """
    Gerencia o ícone da bandeja do sistema.

    Roda em thread daemon separada para não bloquear o loop principal.
    O status é atualizado via set_status() thread-safe.
    """

    def __init__(self, cfg, on_quit: Optional[Callable] = None) -> None:
        self._enabled: bool = cfg.get("ui", "tray_enabled", default=True)
        self._on_quit = on_quit
        self._icon = None
        self._current_status = "idle"
        self._lock = threading.Lock()

    def start(self) -> None:
        if not self._enabled:
            logger.info("Bandeja do sistema desabilitada (ui.tray_enabled=false).")
            return
        thread = threading.Thread(target=self._run, daemon=True, name="tray")
        thread.start()

    def set_status(self, status: str) -> None:
        """Atualiza o ícone da bandeja. Thread-safe."""
        with self._lock:
            if status == self._current_status:
                return
            self._current_status = status

        color = _STATUS_COLORS.get(status, _STATUS_COLORS["idle"])
        label = {
            "idle": "Programador por Voz — Aguardando",
            "recording": "Programador por Voz — Gravando...",
            "processing": "Programador por Voz — Processando...",
            "error": "Programador por Voz — Erro",
        }.get(status, "Programador por Voz")

        if self._icon:
            try:
                self._icon.icon = _make_icon_image(color)
                self._icon.title = label
            except Exception as exc:
                logger.debug("Falha ao atualizar ícone: %s", exc)

    def stop(self) -> None:
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    def _run(self) -> None:
        try:
            import pystray

            def on_quit(icon, item):
                icon.stop()
                if self._on_quit:
                    self._on_quit()

            menu = pystray.Menu(
                pystray.MenuItem("Status: Ocioso", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Sair", on_quit),
            )

            self._icon = pystray.Icon(
                name="programador_por_voz",
                icon=_make_icon_image(_STATUS_COLORS["idle"]),
                title="Programador por Voz — Aguardando",
                menu=menu,
            )
            logger.info("Bandeja do sistema iniciada.")
            self._icon.run()

        except ImportError:
            logger.warning(
                "pystray ou Pillow não instalado. Bandeja desabilitada.\n"
                "Instale: pip install pystray Pillow"
            )
        except Exception as exc:
            logger.error("Erro na bandeja do sistema: %s", exc)
