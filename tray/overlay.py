"""
Overlay flutuante estilo HUD futurista (Jarvis/Iron Man).
Usa tkinter com canvas para desenhar elementos de interface sci-fi.
"""

import threading
import tkinter as tk
import math
from logging_setup import get_logger

logger = get_logger(__name__)

_STATES = {
    "idle":       None,
    "recording":  {"color": "#00ffcc", "text": "OUVINDO", "pulse": True},
    "processing": {"color": "#00aaff", "text": "PROCESSANDO", "pulse": False},
    "error":      {"color": "#ff4444", "text": "ERRO", "pulse": False},
}

W, H = 280, 64
CORNER = 10  # tamanho dos cantos do HUD


class RecordingOverlay:
    def __init__(self):
        self._root = None
        self._canvas = None
        self._thread = None
        self._ready = threading.Event()
        self._state = None
        self._pulse_angle = 0
        self._pulse_job = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True, name="overlay")
        self._thread.start()
        self._ready.wait(timeout=3)

    def set_status(self, status: str):
        if self._root is None:
            return
        cfg = _STATES.get(status)
        try:
            if cfg is None:
                self._root.after(0, self._hide)
            else:
                self._root.after(0, lambda: self._show(cfg))
        except Exception:
            pass

    def stop(self):
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass

    # ── internal ──────────────────────────────────────────────────────────────

    def _run(self):
        try:
            self._root = tk.Tk()
            self._root.overrideredirect(True)
            self._root.attributes("-topmost", True)
            self._root.attributes("-alpha", 0.92)
            self._root.configure(bg="#000000")
            self._root.wm_attributes("-transparentcolor", "#000000")

            self._canvas = tk.Canvas(
                self._root, width=W, height=H,
                bg="#000000", highlightthickness=0
            )
            self._canvas.pack()

            sw = self._root.winfo_screenwidth()
            self._root.geometry(f"{W}x{H}+{sw - W - 24}+24")
            self._root.withdraw()

            self._ready.set()
            self._root.mainloop()
        except Exception as exc:
            logger.warning("Overlay não disponível: %s", exc)
            self._ready.set()

    def _show(self, cfg: dict):
        color = cfg["color"]
        text = cfg["text"]
        pulse = cfg["pulse"]

        self._draw(color, text, pulse_phase=0)
        self._root.deiconify()

        if self._pulse_job:
            self._root.after_cancel(self._pulse_job)
            self._pulse_job = None

        if pulse:
            self._pulse_angle = 0
            self._animate_pulse(color, text)

    def _animate_pulse(self, color: str, text: str):
        self._pulse_angle = (self._pulse_angle + 6) % 360
        alpha = 0.55 + 0.45 * math.sin(math.radians(self._pulse_angle))
        # Modula brilho do ponto pulsante
        r = int(0x00 + (int(color[1:3], 16)) * alpha)
        g = int(0x00 + (int(color[3:5], 16)) * alpha)
        b = int(0x00 + (int(color[5:7], 16)) * alpha)
        pulse_color = f"#{r:02x}{g:02x}{b:02x}"
        self._draw(color, text, pulse_color=pulse_color)
        self._pulse_job = self._root.after(40, lambda: self._animate_pulse(color, text))

    def _draw(self, color: str, text: str, pulse_phase=None, pulse_color=None):
        c = self._canvas
        c.delete("all")

        bg = "#0a0f1a"
        pad = 3

        # Fundo escuro com borda arredondada
        c.create_rectangle(pad, pad, W - pad, H - pad,
                            fill=bg, outline="", width=0)

        # Cantos HUD (4 cantos com linhas em L)
        cl = 12  # comprimento do canto
        lw = 2
        corners = [
            (pad, pad, pad + cl, pad, pad, pad + cl),           # top-left
            (W-pad, pad, W-pad-cl, pad, W-pad, pad+cl),          # top-right
            (pad, H-pad, pad+cl, H-pad, pad, H-pad-cl),          # bottom-left
            (W-pad, H-pad, W-pad-cl, H-pad, W-pad, H-pad-cl),    # bottom-right
        ]
        for x1, y1, x2, y2, x3, y3 in corners:
            c.create_line(x1, y1, x2, y2, fill=color, width=lw)
            c.create_line(x1, y1, x3, y3, fill=color, width=lw)

        # Linha horizontal separadora (tênue)
        c.create_line(pad + cl + 4, H // 2, W - pad - cl - 4, H // 2,
                      fill=color, width=1, dash=(2, 6))

        # Ícone pulsante (círculo)
        dot_x, dot_y = 28, H // 2
        dot_r = 6
        dot_col = pulse_color if pulse_color else color
        c.create_oval(dot_x - dot_r, dot_y - dot_r,
                      dot_x + dot_r, dot_y + dot_r,
                      fill=dot_col, outline=color, width=1)

        # Texto principal
        c.create_text(W // 2 + 10, H // 2,
                      text=text,
                      font=("Courier New", 15, "bold"),
                      fill=color,
                      anchor="center")

        # Label superior esquerdo (marca)
        c.create_text(pad + cl + 6, pad + 7,
                      text="J.A.R.V.I.S",
                      font=("Courier New", 6, "bold"),
                      fill=color,
                      anchor="w")

    def _hide(self):
        if self._pulse_job:
            self._root.after_cancel(self._pulse_job)
            self._pulse_job = None
        if self._root:
            self._root.withdraw()
