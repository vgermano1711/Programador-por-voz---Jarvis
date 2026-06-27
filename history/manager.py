"""
Persiste histórico de comandos em arquivo JSON local.

Formato de cada entrada:
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "type": "dictation" | "control",
  "text": "texto transcrito",
  "command": "CANCELA" (apenas para type=control),
  "success": true/false,
  "language": "pt",
  "inference_ms": 1234
}
"""

import json
import os
from datetime import datetime
from typing import Optional

from logging_setup import get_logger

logger = get_logger(__name__)


class HistoryManager:
    """Gerencia leitura e escrita do arquivo de histórico JSON."""

    def __init__(self, cfg) -> None:
        self._enabled: bool = cfg.get("history", "enabled", default=True)
        self._file: str = cfg.get("history", "file", default="history.json")
        self._max_entries: int = cfg.get("history", "max_entries", default=1000)

    def add(
        self,
        text: str,
        entry_type: str = "dictation",
        command: Optional[str] = None,
        success: bool = True,
        language: Optional[str] = None,
        inference_ms: Optional[int] = None,
    ) -> None:
        """Adiciona entrada ao histórico. Rotaciona se exceder max_entries."""
        if not self._enabled:
            return

        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": entry_type,
            "text": text,
            "success": success,
        }
        if command:
            entry["command"] = command
        if language:
            entry["language"] = language
        if inference_ms is not None:
            entry["inference_ms"] = inference_ms

        try:
            entries = self._load()
            entries.append(entry)

            # Rotação: mantém apenas as últimas N entradas
            if len(entries) > self._max_entries:
                entries = entries[-self._max_entries:]

            self._save(entries)
        except Exception as exc:
            logger.error("Falha ao salvar histórico: %s", exc)

    def get_last(self, n: int = 10) -> list[dict]:
        """Retorna as últimas N entradas do histórico."""
        try:
            return self._load()[-n:]
        except Exception:
            return []

    def get_last_dictation(self) -> Optional[str]:
        """Retorna o texto do último ditado (para comando 'repete')."""
        try:
            entries = self._load()
            for entry in reversed(entries):
                if entry.get("type") == "dictation" and entry.get("success"):
                    return entry.get("text")
        except Exception:
            pass
        return None

    def _load(self) -> list[dict]:
        if not os.path.exists(self._file):
            return []
        with open(self._file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, entries: list[dict]) -> None:
        with open(self._file, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
