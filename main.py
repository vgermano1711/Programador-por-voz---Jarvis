#!/usr/bin/env python3
"""
Programador por Voz — Pipeline Bidirecional de Voz ↔ Claude Code

Fluxo completo:
  [Microfone]
     ↓ (push-to-talk / wake word)
  AudioCapture
     ↓ numpy float32
  Transcriber (faster-whisper)
     ↓ texto transcrito
  CommandInterpreter
     ├── Comando de controle → executa localmente (cancela, interrompe, repete)
     │                         detectar "para de falar" → AudioPlayer.stop()
     └── Ditado literal ──────┬── TextInjector → clipboard → terminal ativo
                              └── ClaudeCapture → `claude --print` → resposta
                                                       ↓
                                                  Humanizer
                                                       ↓ texto para fala
                                                  TTSEngine → bytes WAV
                                                       ↓
                                                  AudioPlayer → fala
                                                       ↓
                                                  AuditLogger

O terminal interativo onde o Claude Code roda continua funcionando normalmente.
O sistema de voz injeta via clipboard E paralelamente chama claude --print para
capturar a resposta e converter em TTS. Veja response_capture/claude_subprocess.py
para a justificativa da abordagem escolhida (subprocess vs pty).
"""

import argparse
import signal
import sys
import threading
import time
from typing import Optional

import numpy as np

from config import load_config
from logging_setup import configure_logging, get_logger
from audio_capture import AudioCapture, list_microphones
from audio_capture.devices import print_microphones
from transcription import Transcriber
from command_interpreter import CommandInterpreter
from command_interpreter.control_commands import ControlCommand, CommandType
from text_injector import TextInjector
from history import HistoryManager
from tray import TrayApp
from tray.overlay import RecordingOverlay
from audit import AuditLogger
from response_capture import ClaudeCapture
from response_humanizer import Humanizer
from tts import create_tts_engine
from tts.player import AudioPlayer
from mcp_servers import MCPManager

logger = get_logger(__name__)


class VoiceProgrammer:
    """
    Orquestra o sistema completo de programação por voz com resposta em áudio.

    Uso básico:
        app = VoiceProgrammer()
        app.run()
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        self._cfg = load_config(config_path)
        self._setup_logging()

        logger.info("Inicializando Programador por Voz (pipeline bidirecional)...")

        # ── Módulos base ────────────────────────────────────────────────────────
        self._history = HistoryManager(self._cfg)
        self._audit = AuditLogger(self._cfg)
        self._injector = TextInjector(self._cfg)
        self._interpreter = CommandInterpreter(self._cfg)
        self._tray = TrayApp(self._cfg, on_quit=self._shutdown)
        self._overlay = RecordingOverlay()

        # ── TTS e player ────────────────────────────────────────────────────────
        self._tts_enabled: bool = self._cfg.get("tts", "enabled", default=True)
        self._tts_engine = None
        self._audio_player = AudioPlayer(
            sample_rate=self._cfg.get("tts", "sample_rate", default=22050)
        )
        self._humanizer = Humanizer(self._cfg)
        self._stop_speaking_phrases: list[str] = self._cfg.get(
            "tts", "stop_speaking_phrases",
            default=["para de falar", "cala a boca", "silencia"]
        )

        # ── Captura de resposta do Claude ───────────────────────────────────────
        self._claude_capture_enabled: bool = self._cfg.get(
            "claude_capture", "enabled", default=True
        )
        self._claude = ClaudeCapture(self._cfg) if self._claude_capture_enabled else None

        # ── MCP ─────────────────────────────────────────────────────────────────
        self._mcp = MCPManager(self._cfg)

        # ── Captura de áudio (último — depende de callbacks acima) ─────────────
        self._capture = AudioCapture(self._cfg, on_audio=self._on_audio)
        def _on_status(status: str):
            self._tray.set_status(status)
            self._overlay.set_status(status)

        self._capture.on_status_change = _on_status

        self._running = False
        self._transcriber: Optional[Transcriber] = None

    def _setup_logging(self) -> None:
        log_cfg = self._cfg.get("logging") or {}
        configure_logging(
            level=log_cfg.get("level", "INFO"),
            log_file=log_cfg.get("file"),
            max_bytes=int(log_cfg.get("max_file_size_mb", 10)) * 1024 * 1024,
            backup_count=log_cfg.get("backup_count", 3),
            console=log_cfg.get("console", True),
        )

    # ── Loop principal ──────────────────────────────────────────────────────────

    def run(self) -> None:
        self._running = True
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self._tray.start()
        self._overlay.start()
        self._tray.set_status("idle")

        # Inicia servidores MCP em background (falha não bloqueia o sistema)
        mcp_thread = threading.Thread(target=self._start_mcp, daemon=True, name="mcp-init")
        mcp_thread.start()

        try:
            self._capture.start()
        except Exception as exc:
            logger.error("Falha ao iniciar captura de áudio: %s", exc)
            _print_startup_help()
            sys.exit(1)

        self._print_banner()

        # Carrega modelos pesados em thread separada para não travar o startup
        init_thread = threading.Thread(
            target=self._load_models, daemon=True, name="model-init"
        )
        init_thread.start()

        while self._running:
            time.sleep(0.1)

        self._cleanup()

    # ── Pipeline de áudio ───────────────────────────────────────────────────────

    def _on_audio(self, audio: np.ndarray, sample_rate: int) -> None:
        """
        Callback chamado quando uma gravação é concluída.
        Executa o pipeline completo de forma thread-safe.
        """
        if self._transcriber is None:
            logger.warning("Modelos ainda carregando... tente novamente em instantes.")
            self._tray.set_status("idle")
            return

        self._tray.set_status("processing")

        # 1. Transcrição
        try:
            result = self._transcriber.transcribe(audio, sample_rate)
        except Exception as exc:
            logger.error("Erro na transcrição: %s", exc)
            self._tray.set_status("error")
            time.sleep(1)
            self._tray.set_status("idle")
            return

        if result is None:
            logger.info("Transcrição vazia (silêncio ou VAD).")
            self._tray.set_status("idle")
            return

        text = result.text
        self._audit.log_voice_input(
            transcribed_text=text,
            duration_ms=int(result.duration_s * 1000),
            language=result.language,
        )
        logger.info("[VOZ] %r", text)

        # 2. Verifica "para de falar" antes de tudo
        if self._is_stop_speaking(text):
            self._audio_player.stop()
            logger.info("Reprodução de áudio interrompida por comando de voz.")
            self._tray.set_status("idle")
            return

        # 3. Interpreta comando
        interpreted = self._interpreter.interpret(text)

        if isinstance(interpreted, ControlCommand):
            self._handle_control(interpreted, text, result)
        else:
            self._handle_dictation(interpreted, text, result)

        self._tray.set_status("idle")

    def _handle_control(
        self, command: ControlCommand, raw_text: str, result
    ) -> None:
        """Executa um comando de controle localmente (sem passar pelo Claude)."""
        ctx = {
            "injector": self._injector,
            "last_dictation": self._interpreter.last_dictation,
        }
        msg = self._interpreter.execute_control(command, ctx)
        logger.info("[CONTROLE] %s → %s", command.type.name, msg)

        self._audit.log_control_command(command.type.name, raw_text)
        self._history.add(
            text=raw_text,
            entry_type="control",
            command=command.type.name,
            success=True,
            language=result.language,
            inference_ms=int(result.inference_time_s * 1000),
        )

        if msg:
            print(f"  [Controle] {msg}")

    def _handle_dictation(self, text: str, raw_text: str, result) -> None:
        """
        Para ditado literal:
        1. Injeta no terminal (para o Claude Code interativo ver)
        2. Paralelamente chama claude --print para capturar resposta e converter em TTS
        """
        # 1. Injeção no terminal ativo
        injected = self._injector.inject(text)
        self._audit.log_action(
            "text_injection", f"Injetou: {text[:80]}", confirmed=True,
            metadata={"success": injected}
        )
        self._history.add(
            text=text,
            entry_type="dictation",
            success=injected,
            language=result.language,
            inference_ms=int(result.inference_time_s * 1000),
        )

        status = "[Injetado]" if injected else "[Falha de injeção]"
        print(f"  {status} {text!r}")

        # 2. Captura resposta do Claude e converte em TTS (em background)
        if self._claude_capture_enabled and self._claude and self._tts_enabled:
            self._claude.send_async(
                user_message=text,
                on_response=self._on_claude_response,
            )

    def _on_claude_response(self, response: str) -> None:
        """Callback quando ClaudeCapture recebe resposta do Claude Code."""
        logger.info("[CLAUDE] %d chars recebidos", len(response))

        # Humaniza a resposta para TTS
        spoken_text = self._humanizer.humanize(response)

        was_truncated = len(spoken_text) < len(response) - 50
        self._audit.log_claude_response(
            response_text=response,
            inference_ms=0,
            was_truncated=was_truncated,
        )

        if not spoken_text:
            logger.debug("Resposta do Claude não tem conteúdo falável após humanização.")
            return

        print(f"\n  [Claude → Voz] {spoken_text[:100]}{'...' if len(spoken_text) > 100 else ''}")

        # Síntese e reprodução
        self._speak(spoken_text)

    def _speak(self, text: str) -> None:
        """Converte texto em áudio e toca."""
        if not self._tts_engine:
            logger.warning("TTS não carregado ainda. Resposta não será falada.")
            return

        try:
            audio_bytes = self._tts_engine.synthesize(text)
            self._audio_player.play(audio_bytes)

            self._audit.log_tts_output(
                spoken_text=text,
                engine=self._tts_engine.name,
            )
        except Exception as exc:
            logger.error("Erro no TTS: %s", exc)

    def _is_stop_speaking(self, text: str) -> bool:
        """Verifica se o texto é um comando para parar o áudio em andamento."""
        import unicodedata, re
        normalized = re.sub(r"[^\w\s]", "", unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode()).lower().strip()
        for phrase in self._stop_speaking_phrases:
            if phrase.lower() in normalized:
                return True
        return False

    # ── Inicialização dos modelos ────────────────────────────────────────────────

    def _load_models(self) -> None:
        """Carrega Whisper e TTS em thread separada (são lentos para carregar)."""
        print("  Carregando modelos... aguarde.")

        # Whisper
        try:
            self._transcriber = Transcriber(self._cfg)
            print("  ✓ Whisper carregado.")
        except Exception as exc:
            logger.error("Falha ao carregar Whisper: %s", exc)
            self._tray.set_status("error")

        # TTS (opcional — falha não impede o sistema de funcionar)
        if self._tts_enabled:
            try:
                self._tts_engine = create_tts_engine(self._cfg)
                if self._tts_engine.is_available():
                    print(f"  ✓ TTS carregado ({self._tts_engine.name}).")
                else:
                    print("  ⚠ TTS não disponível — respostas não serão faladas.")
            except Exception as exc:
                logger.warning("TTS não carregado: %s — sistema continua sem voz de saída.", exc)

        if self._transcriber:
            print("\n  Sistema pronto! Pressione F9 e fale.\n")

    def _start_mcp(self) -> None:
        """Inicia servidores MCP. Executado em thread separada."""
        results = self._mcp.start_all()
        if results:
            for name, ok in results.items():
                status = "✓" if ok else "✗"
                print(f"  {status} MCP {name}: {'ativo' if ok else 'falhou'}")

    # ── Saída ───────────────────────────────────────────────────────────────────

    def _print_banner(self) -> None:
        mode = self._cfg.get("activation", "mode", default="push_to_talk")
        key = self._cfg.get("activation", "push_to_talk_key", default="f9")
        model = self._cfg.get("transcription", "model", default="small")
        tts_engine = self._cfg.get("tts", "engine", default="coqui")
        capture = "sim" if self._claude_capture_enabled else "não"

        print(f"\n{'='*62}")
        print("  Programador por Voz — Pipeline Bidirecional")
        print(f"{'='*62}")
        print(f"  Modo entrada:  {mode} ({key.upper() if mode == 'push_to_talk' else 'wake word'})")
        print(f"  STT:           Whisper {model}")
        print(f"  TTS:           {tts_engine} {'(habilitado)' if self._tts_enabled else '(desabilitado)'}")
        print(f"  Resposta voz:  {capture}")
        print(f"  Audit log:     {self._cfg.get('audit', 'file', default='audit_log.jsonl')}")
        print(f"{'='*62}")
        print("  Ctrl+C para sair | 'para de falar' para silenciar TTS")
        print()

    def _signal_handler(self, signum, frame) -> None:
        logger.info("Sinal %d recebido. Encerrando...", signum)
        self._shutdown()

    def _shutdown(self) -> None:
        self._running = False

    def _cleanup(self) -> None:
        logger.info("Encerrando sistema...")
        self._audio_player.stop()
        try:
            self._capture.stop()
        except Exception:
            pass
        try:
            self._mcp.stop_all()
        except Exception:
            pass
        try:
            self._tray.stop()
        except Exception:
            pass
        logger.info("Sistema encerrado.")


# ── CLI ─────────────────────────────────────────────────────────────────────────

def _print_startup_help() -> None:
    print("\n[ERRO] Falha ao iniciar captura de áudio.")
    print("Causas comuns:")
    print("  - Nenhum microfone conectado")
    print("  - Permissão negada ao microfone")
    print("  - sounddevice não instalado: pip install sounddevice")
    print("\nListagem de dispositivos: python main.py --list-devices\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Programador por Voz — pipeline bidirecional de voz ↔ Claude Code"
    )
    parser.add_argument("--config", "-c", default=None, help="Caminho para config.yaml")
    parser.add_argument("--list-devices", action="store_true", help="Lista microfones e sai")
    parser.add_argument("--model", default=None, help="Modelo Whisper (tiny/base/small/medium/large-v3)")
    parser.add_argument("--no-tts", action="store_true", help="Desabilita saída de voz (TTS)")
    parser.add_argument("--no-capture", action="store_true", help="Desabilita captura de resposta do Claude")
    parser.add_argument("--debug", action="store_true", help="Logging nível DEBUG")
    args = parser.parse_args()

    if args.list_devices:
        print_microphones()
        sys.exit(0)

    if args.debug:
        configure_logging(level="DEBUG")

    app = VoiceProgrammer(config_path=args.config)

    if args.model:
        app._cfg.set(args.model, "transcription", "model")
    if args.no_tts:
        app._cfg.set(False, "tts", "enabled")
    if args.no_capture:
        app._cfg.set(False, "claude_capture", "enabled")
    if args.debug:
        app._cfg.set("DEBUG", "logging", "level")

    app.run()


if __name__ == "__main__":
    main()
