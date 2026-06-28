"""
Captura a resposta do Claude Code via subprocess (modo --print).

Decisão arquitetural documentada:

ABORDAGEM ESCOLHIDA: subprocess com `claude --print`
  Prós:
    - Texto limpo em stdout, sem escape codes ANSI nem race conditions
    - Determinístico: sabemos exatamente quando a resposta terminou (EOF)
    - Testável em isolamento com mock de subprocess
    - Contexto de sessão mantido via --session-id (quando disponível)
  Contras:
    - Executa uma instância separada do Claude Code por chamada de voz
      → cada resposta não tem memória das anteriores EXCETO se passarmos
        o histórico manualmente ou usarmos flags de sessão do CLI
    - Perde a experiência do terminal interativo (não dá para ver o Claude
      Code "pensando" na tela enquanto processa)
    - Latência adicional de ~200ms para spawn do processo

ABORDAGEM DESCARTADA: captura via pty/tmux
  Contras que pesaram:
    - Parsing complexo de sequências de escape ANSI (ESC[...m, etc.)
    - Race condition: como saber quando o Claude terminou de responder?
      (o terminal não emite sinal de "fim de turno" — precisaríamos de
       heurística de timeout ou detecção de prompt, ambas frágeis)
    - Breakage garantida a cada mudança de formatação do Claude Code
    - OCR seria ainda pior: lento, impreciso, quebra com qualquer mudança de fonte

DECISÃO FINAL: subprocess para TTS + terminal interativo para visualização.
  O usuário mantém uma sessão interativa normal no terminal para ver o histórico
  visual completo, enquanto o script injeta via clipboard (já implementado) E
  paralelamente chama `claude --print` para capturar a resposta e converter em TTS.

  Limitação real: as duas "instâncias" (terminal interativo + subprocess) não
  compartilham contexto de conversa automaticamente. Para manter contexto, o
  script mantém um histórico local de mensagens e passa como --system ou via
  arquivo de contexto no próximo call. Isso é documentado como limitação.
"""

import subprocess
import threading
import time
from typing import Callable, Iterator, Optional

from logging_setup import get_logger

logger = get_logger(__name__)

# Callbacks
ResponseCallback = Callable[[str], None]
ChunkCallback = Callable[[str], None]


class ClaudeCapture:
    """
    Envia mensagem ao Claude Code via subprocess e captura a resposta.

    Mantém histórico de mensagens para simular continuidade de sessão
    (já que cada chamada `claude --print` é independente).
    """

    def __init__(self, cfg) -> None:
        self._claude_bin: str = cfg.get("claude_capture", "claude_bin", default="claude")
        self._timeout: int = cfg.get("claude_capture", "timeout_seconds", default=60)
        self._system_prompt: str = cfg.get("claude_capture", "system_prompt", default="")
        self._max_history: int = cfg.get("claude_capture", "max_history_turns", default=10)

        # Histórico local de pares (user, assistant) para simular contexto
        self._history: list[dict] = []

    def send_streaming(
        self,
        user_message: str,
        on_chunk: ChunkCallback,
    ) -> Optional[str]:
        """
        Envia mensagem e chama on_chunk com cada linha conforme chega do processo.
        Retorna a resposta completa quando terminar.
        Ideal para alimentar o StreamingTTSPipeline linha a linha.
        """
        args = self._build_args(user_message)
        logger.debug("Chamando Claude (streaming): %s ...", " ".join(args[:3]))

        full_response: list[str] = []
        t_start = time.monotonic()

        try:
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,  # line-buffered
            )

            first_chunk = True
            for line in process.stdout:
                if first_chunk:
                    logger.debug("Claude primeiro chunk em %.2fs", time.monotonic() - t_start)
                    first_chunk = False
                full_response.append(line)
                try:
                    on_chunk(line)
                except Exception as exc:
                    logger.error("Erro em on_chunk: %s", exc)

            process.wait(timeout=self._timeout)

            if process.returncode != 0:
                stderr = process.stderr.read().strip()
                logger.error("claude retornou %d: %s", process.returncode, stderr)
                return None

            response = "".join(full_response).strip()
            if response:
                self._add_to_history(user_message, response)
            logger.debug("Claude resposta completa em %.2fs", time.monotonic() - t_start)
            return response or None

        except subprocess.TimeoutExpired:
            process.kill()
            logger.error("Claude não respondeu em %ds.", self._timeout)
            return None
        except FileNotFoundError:
            logger.error("Binário '%s' não encontrado.", self._claude_bin)
            return None
        except Exception as exc:
            logger.error("Erro ao chamar Claude Code: %s", exc)
            return None

    def send_streaming_async(
        self,
        user_message: str,
        on_chunk: ChunkCallback,
        on_done: Optional[ResponseCallback] = None,
    ) -> threading.Thread:
        """Versão não-bloqueante de send_streaming. Dispara on_done ao terminar."""
        def worker():
            response = self.send_streaming(user_message, on_chunk)
            if on_done:
                try:
                    on_done(response)  # chamado sempre, mesmo se response=None (falha)
                except Exception as exc:
                    logger.error("Erro em on_done: %s", exc)

        thread = threading.Thread(target=worker, daemon=True, name="claude-stream")
        thread.start()
        return thread

    def send_async(self, user_message: str, on_response: ResponseCallback) -> threading.Thread:
        """
        Envia mensagem em thread separada e chama on_response quando terminar.
        Não bloqueia o loop principal de captura de voz.
        """
        thread = threading.Thread(
            target=self._send_and_callback,
            args=(user_message, on_response),
            daemon=True,
            name="claude-capture",
        )
        thread.start()
        return thread

    def send(self, user_message: str) -> Optional[str]:
        """
        Envia mensagem de forma síncrona e retorna a resposta.
        Use send_async() no pipeline principal para não bloquear.
        """
        args = self._build_args(user_message)
        logger.debug("Chamando Claude: %s", " ".join(args[:3]) + " ...")

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self._timeout,
            )

            if result.returncode != 0:
                stderr = result.stderr.strip()
                logger.error(
                    "claude --print retornou código %d: %s", result.returncode, stderr
                )
                if "not found" in stderr.lower() or result.returncode == 127:
                    logger.error(
                        "Claude Code CLI não encontrado. Instale com:\n"
                        "  npm install -g @anthropic-ai/claude-code\n"
                        "Ou verifique se 'claude' está no PATH."
                    )
                return None

            response = result.stdout.strip()
            if response:
                self._add_to_history(user_message, response)
            return response or None

        except subprocess.TimeoutExpired:
            logger.error("Claude Code não respondeu em %ds.", self._timeout)
            return None
        except FileNotFoundError:
            logger.error(
                "Binário '%s' não encontrado. Verifique o PATH ou defina "
                "claude_capture.claude_bin no config.yaml.", self._claude_bin
            )
            return None
        except Exception as exc:
            logger.error("Erro ao chamar Claude Code: %s", exc)
            return None

    def _build_args(self, user_message: str) -> list[str]:
        """Monta os argumentos do subprocess com histórico de contexto."""
        # Constrói prompt com histórico para simular continuidade
        full_prompt = self._build_prompt_with_history(user_message)

        args = [self._claude_bin, "--print", full_prompt]

        if self._system_prompt:
            args.extend(["--system", self._system_prompt])

        return args

    def _build_prompt_with_history(self, new_message: str) -> str:
        """
        Serializa histórico recente + nova mensagem em texto único.
        Isso é necessário porque `claude --print` não mantém estado entre calls.
        Limitação: histórico longo pode exceder a janela de contexto.
        """
        if not self._history:
            return new_message

        lines = []
        recent = self._history[-self._max_history:]
        for turn in recent:
            lines.append(f"Usuário: {turn['user']}")
            lines.append(f"Assistente: {turn['assistant']}")
        lines.append(f"Usuário: {new_message}")

        return "\n".join(lines)

    def _add_to_history(self, user: str, assistant: str) -> None:
        self._history.append({"user": user, "assistant": assistant})
        # Rotação de histórico
        if len(self._history) > self._max_history * 2:
            self._history = self._history[-self._max_history:]

    def _send_and_callback(self, user_message: str, on_response: ResponseCallback) -> None:
        response = self.send(user_message)
        if response:
            try:
                on_response(response)
            except Exception as exc:
                logger.error("Erro no callback de resposta: %s", exc)

    def clear_history(self) -> None:
        """Limpa o histórico de conversa (útil para iniciar novo tópico)."""
        self._history = []
        logger.info("Histórico de conversa limpo.")
