"""
Cliente direto da API Anthropic — substitui o subprocess claude --print.
Mais confiável, sem crashes no Windows, funciona fora do Claude Code.
"""

import os
import threading
from typing import Callable, Iterator, Optional

from logging_setup import get_logger

logger = get_logger(__name__)

ResponseCallback = Callable[[str], None]
ChunkCallback = Callable[[str], None]


class AnthropicClient:
    """
    Envia mensagens ao Claude via API Anthropic diretamente.
    Mantém histórico de conversa entre chamadas.
    """

    DEFAULT_MODEL = "claude-sonnet-4-6"
    DEFAULT_MAX_TOKENS = 1024

    def __init__(self, cfg) -> None:
        self._api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
        self._model: str = cfg.get("claude_capture", "model", default=self.DEFAULT_MODEL)
        self._max_tokens: int = cfg.get("claude_capture", "max_tokens", default=self.DEFAULT_MAX_TOKENS)
        self._timeout: int = cfg.get("claude_capture", "timeout_seconds", default=60)
        self._max_history: int = cfg.get("claude_capture", "max_history_turns", default=10)
        self._system_prompt: str = self._load_system_prompt(cfg)

        self._history: list[dict] = []
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        if not self._api_key:
            logger.error("ANTHROPIC_API_KEY não encontrada. Configure a variável de ambiente.")
            return
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._api_key)
            logger.info("Cliente Anthropic inicializado (modelo: %s)", self._model)
        except ImportError:
            logger.error("Pacote 'anthropic' não instalado. Execute: python -m pip install anthropic")

    def _load_system_prompt(self, cfg) -> str:
        """Carrega CLAUDE.md do diretório do projeto como system prompt."""
        import pathlib
        claude_md = pathlib.Path(__file__).parent.parent / "CLAUDE.md"
        if claude_md.exists():
            return claude_md.read_text(encoding="utf-8")
        fallback = cfg.get("claude_capture", "system_prompt", default="")
        return fallback

    def send(self, user_message: str) -> Optional[str]:
        """Envia mensagem e retorna resposta completa."""
        if not self._client:
            logger.error("Cliente Anthropic não inicializado.")
            return None
        try:
            messages = self._build_messages(user_message)
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=self._system_prompt,
                messages=messages,
            )
            text = response.content[0].text if response.content else None
            if text:
                self._add_to_history(user_message, text)
            return text
        except Exception as exc:
            logger.error("Erro na API Anthropic: %s", exc)
            return None

    def send_streaming(self, user_message: str, on_chunk: ChunkCallback) -> Optional[str]:
        """Envia mensagem e chama on_chunk com cada fragmento de texto."""
        if not self._client:
            logger.error("Cliente Anthropic não inicializado.")
            return None
        try:
            messages = self._build_messages(user_message)
            full_text: list[str] = []

            with self._client.messages.stream(
                model=self._model,
                max_tokens=self._max_tokens,
                system=self._system_prompt,
                messages=messages,
            ) as stream:
                for text_chunk in stream.text_stream:
                    full_text.append(text_chunk)
                    try:
                        on_chunk(text_chunk)
                    except Exception as exc:
                        logger.error("Erro em on_chunk: %s", exc)

            response = "".join(full_text).strip()
            if response:
                self._add_to_history(user_message, response)
            return response or None

        except Exception as exc:
            logger.error("Erro no streaming da API Anthropic: %s", exc)
            return None

    def send_streaming_async(
        self,
        user_message: str,
        on_chunk: ChunkCallback,
        on_done: Optional[ResponseCallback] = None,
    ) -> threading.Thread:
        """Versão não-bloqueante de send_streaming."""
        def worker():
            response = self.send_streaming(user_message, on_chunk)
            if on_done:
                try:
                    on_done(response)
                except Exception as exc:
                    logger.error("Erro em on_done: %s", exc)

        thread = threading.Thread(target=worker, daemon=True, name="jarvis-api")
        thread.start()
        return thread

    def send_async(self, user_message: str, on_response: ResponseCallback) -> threading.Thread:
        """Envia mensagem em thread separada."""
        def worker():
            response = self.send(user_message)
            if response:
                try:
                    on_response(response)
                except Exception as exc:
                    logger.error("Erro no callback: %s", exc)

        thread = threading.Thread(target=worker, daemon=True, name="jarvis-api")
        thread.start()
        return thread

    def clear_history(self) -> None:
        self._history = []
        logger.info("Histórico limpo.")

    def _build_messages(self, new_message: str) -> list[dict]:
        messages = []
        for turn in self._history[-self._max_history:]:
            messages.append({"role": "user", "content": turn["user"]})
            messages.append({"role": "assistant", "content": turn["assistant"]})
        messages.append({"role": "user", "content": new_message})
        return messages

    def _add_to_history(self, user: str, assistant: str) -> None:
        self._history.append({"user": user, "assistant": assistant})
        if len(self._history) > self._max_history * 2:
            self._history = self._history[-self._max_history:]
