import re
import threading
import time
from collections import deque
from typing import Callable, Optional

from logging_setup import get_logger

logger = get_logger(__name__)

_ERROR_PATTERN = re.compile(r"(ERROR|EXCEPTION|Traceback)", re.IGNORECASE)
_TRACEBACK_PATTERN = re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE)
_DEDUP_WINDOW_SECONDS = 30


class ProactiveMonitor:
    """
    Monitora saída do terminal, arquivo de log e clipboard em busca de erros,
    disparando um callback quando algo relevante é detectado.
    """

    def __init__(self, log_file: str = "programador_por_voz.log") -> None:
        self._log_file = log_file
        self._on_alert: Optional[Callable[[str], None]] = None
        self._running = False
        self._threads: list[threading.Thread] = []
        self._recent_alerts: deque[tuple[str, float]] = deque(maxlen=100)
        self._lock = threading.Lock()

    def start(self, on_alert: Callable[[str], None]) -> None:
        self._on_alert = on_alert
        self._running = True

        log_thread = threading.Thread(target=self._watch_log_file, daemon=True, name="proactive-log-watcher")
        clip_thread = threading.Thread(target=self._watch_clipboard, daemon=True, name="proactive-clipboard-watcher")

        self._threads = [log_thread, clip_thread]
        for t in self._threads:
            t.start()

        logger.info("ProactiveMonitor iniciado (log=%s)", self._log_file)

    def stop(self) -> None:
        self._running = False
        logger.info("ProactiveMonitor parado.")

    def add_output_line(self, line: str) -> None:
        if _ERROR_PATTERN.search(line):
            self._maybe_alert(self._summarize_line(line))

    def _maybe_alert(self, message: str) -> None:
        now = time.monotonic()
        with self._lock:
            for prev_msg, prev_time in self._recent_alerts:
                if prev_msg == message and (now - prev_time) < _DEDUP_WINDOW_SECONDS:
                    return
            self._recent_alerts.append((message, now))

        if self._on_alert:
            try:
                self._on_alert(message)
            except Exception as exc:
                logger.error("Erro no callback on_alert: %s", exc)

    def _summarize_line(self, line: str) -> str:
        line = line.strip()
        if len(line) > 120:
            return line[:120] + "..."
        return line

    def _watch_log_file(self) -> None:
        try:
            import os
            last_pos = 0
            while self._running:
                try:
                    if os.path.exists(self._log_file):
                        with open(self._log_file, "r", encoding="utf-8", errors="replace") as f:
                            f.seek(last_pos)
                            for raw_line in f:
                                if _ERROR_PATTERN.search(raw_line):
                                    self._maybe_alert(self._summarize_line(raw_line))
                            last_pos = f.tell()
                except OSError as exc:
                    logger.debug("Erro ao ler log file: %s", exc)
                time.sleep(1)
        except Exception as exc:
            logger.error("_watch_log_file encerrado inesperadamente: %s", exc)

    def _watch_clipboard(self) -> None:
        try:
            import pyperclip
        except ImportError:
            logger.warning("pyperclip não instalado — monitoramento de clipboard desativado.")
            return

        last_content = ""
        while self._running:
            try:
                content = pyperclip.paste()
                if content != last_content and _TRACEBACK_PATTERN.search(content):
                    first_line = next(
                        (ln.strip() for ln in content.splitlines() if ln.strip()),
                        "Stack trace detectado no clipboard",
                    )
                    self._maybe_alert(f"[clipboard] {first_line[:100]}")
                last_content = content
            except Exception as exc:
                logger.debug("Erro ao ler clipboard: %s", exc)
            time.sleep(2)
