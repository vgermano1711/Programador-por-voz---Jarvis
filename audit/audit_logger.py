"""
Log de auditoria de todas as interações do sistema.

Mantém rastreabilidade completa: o que foi falado, o que o Claude respondeu,
qual ação foi tomada — essencial para segurança e debugging.

Formato de cada entrada:
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "session_id": "uuid",
  "event_type": "voice_input" | "claude_response" | "tts_output" | "control_command" | "action_taken",
  "content": "texto do evento",
  "metadata": {...},
  "confirmed": true/false  # para ações irreversíveis
}
"""

import json
import os
import uuid
from datetime import datetime
from typing import Any, Optional

from logging_setup import get_logger

logger = get_logger(__name__)


class AuditLogger:
    """
    Registra todos os eventos do sistema de voz com rastreabilidade completa.

    Uma instância por sessão — gera session_id único para agrupar
    todos os eventos de uma execução do programa.
    """

    def __init__(self, cfg) -> None:
        self._enabled: bool = cfg.get("audit", "enabled", default=True)
        self._file: str = cfg.get("audit", "file", default="audit_log.jsonl")
        self._max_size_mb: int = cfg.get("audit", "max_size_mb", default=50)
        self._session_id: str = str(uuid.uuid4())[:8]  # 8 chars é suficiente
        self._entry_count = 0

        if self._enabled:
            logger.info("AuditLogger iniciado (session=%s, file=%s)", self._session_id, self._file)

    # ── Eventos de entrada de voz ───────────────────────────────────────────────

    def log_voice_input(self, transcribed_text: str, duration_ms: int, language: str = "pt") -> None:
        """Registra texto capturado pela entrada de voz."""
        self._log("voice_input", transcribed_text, metadata={
            "duration_ms": duration_ms,
            "language": language,
        })

    def log_control_command(self, command_name: str, raw_text: str) -> None:
        """Registra execução de comando de controle (cancela, interrompe, etc.)."""
        self._log("control_command", raw_text, metadata={"command": command_name})

    # ── Eventos de resposta do Claude ───────────────────────────────────────────

    def log_claude_response(
        self,
        response_text: str,
        inference_ms: int,
        was_truncated: bool = False,
    ) -> None:
        """Registra resposta recebida do Claude Code."""
        self._log("claude_response", response_text, metadata={
            "inference_ms": inference_ms,
            "char_count": len(response_text),
            "was_truncated": was_truncated,
        })

    def log_tts_output(self, spoken_text: str, engine: str, duration_ms: Optional[int] = None) -> None:
        """Registra texto que foi convertido em áudio e falado."""
        self._log("tts_output", spoken_text, metadata={
            "engine": engine,
            "duration_ms": duration_ms,
        })

    # ── Eventos de ação ─────────────────────────────────────────────────────────

    def log_action(
        self,
        action_type: str,
        description: str,
        confirmed: bool = True,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Registra ação tomada pelo sistema (injeção de texto, MCP call, etc.).
        confirmed=False indica ação que foi solicitada mas não confirmada pelo usuário.
        """
        self._log("action_taken", description, confirmed=confirmed, metadata={
            "action_type": action_type,
            **(metadata or {}),
        })

    def log_external_action(
        self,
        action_type: str,
        description: str,
        confirmed: bool,
        destination: str,
    ) -> None:
        """
        Registra ação que envia dados para fora do computador.
        Requer confirmed=True para ser considerada executada.
        """
        self._log(
            "external_action",
            description,
            confirmed=confirmed,
            metadata={
                "action_type": action_type,
                "destination": destination,
                "REQUIRES_CONFIRMATION": True,
            }
        )
        if not confirmed:
            logger.warning(
                "Ação externa '%s' → '%s' bloqueada: aguardando confirmação do usuário.",
                action_type, destination
            )

    # ── Internos ────────────────────────────────────────────────────────────────

    def _log(
        self,
        event_type: str,
        content: str,
        confirmed: bool = True,
        metadata: Optional[dict] = None,
    ) -> None:
        if not self._enabled:
            return

        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self._session_id,
            "event_type": event_type,
            "content": content,
            "confirmed": confirmed,
        }
        if metadata:
            entry["metadata"] = metadata

        try:
            self._rotate_if_needed()
            with open(self._file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._entry_count += 1
        except Exception as exc:
            logger.error("Falha ao escrever audit log: %s", exc)

    def _rotate_if_needed(self) -> None:
        """Rotaciona o arquivo de log se exceder o tamanho máximo."""
        try:
            if os.path.exists(self._file):
                size_mb = os.path.getsize(self._file) / (1024 * 1024)
                if size_mb > self._max_size_mb:
                    backup = self._file.replace(".jsonl", f".{datetime.now().strftime('%Y%m%d%H%M%S')}.jsonl")
                    os.rename(self._file, backup)
                    logger.info("Audit log rotacionado para %s.", backup)
        except Exception:
            pass

    @property
    def session_id(self) -> str:
        return self._session_id
