"""
Overlay flutuante que aparece na tela durante gravação.

Uma janela pequena e semi-transparente no canto da tela mostra
o estado atual: gravando (vermelho) ou processando (azul).
Usa tkinter (incluso no Python, sem dependências extras).
"""

import threading
import tkinter as tk
from logging_setup import get_logger

logger = get_logger(__name__)

_COLORS = {
    "idle":       None,               # esconde
    "recording":  ("#cc2222", "● GRAVANDO"),
    "processing": ("#1a7acc", "⏳ PROCESSANDO"),
    "error":      ("#ff8800", "✗ ERRO"),
}


class RecordingOverlay:
    """Janela flutuante que indica o estado de gravação."""

    def __init__(self):
        self._root = None
        self._label = None
        self._thread = None
        self._ready = threading.Event()
        self._lock = threading.Lock()

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True, name="overlay")
        self._thread.start()
        self._ready.wait(timeout=3)

    def set_status(self, status: str):
        if self._root is None:
            return
        config = _COLORS.get(status)
        try:
            if config is None:
                self._root.after(0, self._hide)
            else:
                color, text = config
                self._root.after(0, lambda: self._show(color, text))
        except Exception:
            pass

    def stop(self):
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass

    def _run(self):
        try:
            self._root = tk.Tk()
            self._root.overrideredirect(True)       # sem barra de título
            self._root.attributes("-topmost", True) # sempre na frente
            self._root.attributes("-alpha", 0.85)   # semi-transparente
            self._root.configure(bg="#222222")
            self._root.withdraw()                   # começa escondida

            self._label = tk.Label(
                self._root,
                text="",
                font=("Segoe UI", 13, "bold"),
                fg="white",
                bg="#222222",
                padx=16,
                pady=8,
            )
            self._label.pack()

            # Posiciona no canto superior direito
            self._root.update_idletasks()
            sw = self._root.winfo_screenwidth()
            self._root.geometry(f"+{sw - 260}+40")

            self._ready.set()
            self._root.mainloop()
        except Exception as exc:
            logger.warning("Overlay não disponível: %s", exc)
            self._ready.set()

    def _show(self, color: str, text: str):
        if self._root and self._label:
            self._label.configure(text=text, bg=color)
            self._root.configure(bg=color)
            self._root.deiconify()
            self._root.update_idletasks()
            sw = self._root.winfo_screenwidth()
            w = self._root.winfo_width() + 32
            self._root.geometry(f"+{sw - w}+40")

    def _hide(self):
        if self._root:
            self._root.withdraw()
