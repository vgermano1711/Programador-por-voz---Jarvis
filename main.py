#!/usr/bin/env python3
"""
Programador por Voz — Ponto de entrada principal.

Fluxo do pipeline:
  [Microfone] → AudioCapture → [numpy float32]
  → Transcriber → [TranscriptionResult]
  → CommandInterpreter → [str | ControlCommand]
  → TextInjector / ControlHandler
  → HistoryManager

Todos os erros em cada etapa são capturados localmente para não
interromper o loop principal. O sistema continua rodando mesmo que
uma transcrição falhe ou o terminal não responda.
"""

import argparse
import signal
import sys
import time

import numpy as np

from config import load_config
from logging_setup import configure_logging, get_logger
from audio_capture import AudioCapture, list_microphones
from audio_capture.devices import print_microphones
from transcription import Transcriber
from command_interpreter import CommandInterpreter
from command_interpreter.control_commands import CommandType
from text_injector import TextInjector
from history import HistoryManager
from tray import TrayApp

logger = get_logger(__name__)


class VoiceProgrammer:
    """
    Orquestra todos os módulos do sistema de programação por voz.

    Uso básico:
        app = VoiceProgrammer()
        app.run()  # Bloqueia até Ctrl+C ou sair pela bandeja
    """

    def __init__(self, config_path: str = None) -> None:
        self._cfg = load_config(config_path)
        self._setup_logging()

        logger.info("Inicializando Programador por Voz...")

        self._history = HistoryManager(self._cfg)
        self._injector = TextInjector(self._cfg)
        self._interpreter = CommandInterpreter(self._cfg)
        self._tray = TrayApp(self._cfg, on_quit=self._shutdown)
        self._capture = AudioCapture(self._cfg, on_audio=self._on_audio)

        # Conecta callback de status da captura → bandeja
        self._capture.on_status_change = self._tray.set_status

        self._running = False

    def _setup_logging(self) -> None:
        log_cfg = self._cfg.get("logging") or {}
        configure_logging(
            level=log_cfg.get("level", "INFO"),
            log_file=log_cfg.get("file"),
            max_bytes=int(log_cfg.get("max_file_size_mb", 10)) * 1024 * 1024,
            backup_count=log_cfg.get("backup_count", 3),
            console=log_cfg.get("console", True),
        )

    def run(self) -> None:
        """Loop principal. Bloqueia até sinal de shutdown."""
        self._running = True

        # Instala handlers de sinal para encerramento limpo
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self._tray.start()
        self._tray.set_status("idle")

        try:
            self._capture.start()
        except Exception as exc:
            logger.error("Falha ao iniciar captura de áudio: %s", exc)
            self._print_startup_help()
            sys.exit(1)

        mode = self._cfg.get("activation", "mode", default="push_to_talk")
        key = self._cfg.get("activation", "push_to_talk_key", default="f9")
        model = self._cfg.get("transcription", "model", default="small")

        print(f"\n{'='*60}")
        print("  Programador por Voz — Ativo")
        print(f"{'='*60}")
        print(f"  Modo:    {mode}")
        if mode == "push_to_talk":
            print(f"  Tecla:   {key.upper()} (segurar para gravar, soltar para transcrever)")
        print(f"  Modelo:  Whisper {model}")
        print(f"  Idioma:  Português (pt)")
        print(f"{'='*60}")
        print("  Pressione Ctrl+C para sair.")
        print()

        try:
            self._load_transcriber()
        except Exception as exc:
            logger.error("Falha ao carregar modelo Whisper: %s", exc)
            self._tray.set_status("error")
            self._shutdown()
            return

        while self._running:
            time.sleep(0.1)

        self._cleanup()

    def _load_transcriber(self) -> None:
        """Carrega o modelo Whisper (pode demorar alguns segundos)."""
        print("Carregando modelo Whisper... aguarde.")
        self._transcriber = Transcriber(self._cfg)
        print("Modelo carregado. Sistema pronto!\n")

    # ── Pipeline de processamento de áudio ──────────────────────────────────────

    def _on_audio(self, audio: np.ndarray, sample_rate: int) -> None:
        """
        Callback chamado quando uma gravação push-to-talk é concluída.
        Executa o pipeline completo: transcrição → interpretação → injeção.
        """
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
            logger.info("Transcrição retornou vazio (silêncio ou VAD).")
            self._tray.set_status("idle")
            return

        text = result.text
        logger.info("Transcrito: %r", text)

        # 2. Interpretação de comando
        interpreted = self._interpreter.interpret(text)

        from command_interpreter.control_commands import ControlCommand

        if isinstance(interpreted, ControlCommand):
            # Comando de controle
            ctx = {
                "injector": self._injector,
                "last_dictation": self._interpreter.last_dictation,
            }
            msg = self._interpreter.execute_control(interpreted, ctx)
            logger.info("Comando de controle executado: %s → %s", interpreted.type.name, msg)

            self._history.add(
                text=text,
                entry_type="control",
                command=interpreted.type.name,
                success=True,
                language=result.language,
                inference_ms=int(result.inference_time_s * 1000),
            )

            if msg:
                print(f"[Controle] {msg}")

        else:
            # Ditado literal — injeta no terminal
            success = self._injector.inject(interpreted)

            self._history.add(
                text=interpreted,
                entry_type="dictation",
                success=success,
                language=result.language,
                inference_ms=int(result.inference_time_s * 1000),
            )

            if success:
                print(f"[Injetado] {interpreted!r}")
            else:
                print(f"[Erro] Falha ao injetar: {interpreted!r}")
                self._tray.set_status("error")
                time.sleep(1)

        self._tray.set_status("idle")

    # ── Encerramento ────────────────────────────────────────────────────────────

    def _signal_handler(self, signum, frame) -> None:
        logger.info("Sinal %d recebido. Encerrando...", signum)
        self._shutdown()

    def _shutdown(self) -> None:
        self._running = False

    def _cleanup(self) -> None:
        logger.info("Encerrando sistema...")
        try:
            self._capture.stop()
        except Exception as exc:
            logger.debug("Erro ao parar captura: %s", exc)
        try:
            self._tray.stop()
        except Exception:
            pass
        logger.info("Sistema encerrado.")

    @staticmethod
    def _print_startup_help() -> None:
        print("\n[ERRO] Falha ao iniciar captura de áudio.")
        print("Possíveis causas:")
        print("  - Nenhum microfone conectado")
        print("  - Permissão negada ao microfone")
        print("  - sounddevice não instalado: pip install sounddevice")
        print("\nListagem de dispositivos: python main.py --list-devices\n")


# ── CLI ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Programador por Voz — Transcrição de fala para comandos no terminal"
    )
    parser.add_argument(
        "--config", "-c", default=None,
        help="Caminho para arquivo de configuração (padrão: config.yaml)",
    )
    parser.add_argument(
        "--list-devices", action="store_true",
        help="Lista microfones disponíveis e sai",
    )
    parser.add_argument(
        "--model", default=None,
        help="Sobrescreve o modelo Whisper (tiny/base/small/medium/large-v3)",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Ativa logging em nível DEBUG",
    )
    args = parser.parse_args()

    if args.list_devices:
        print_microphones()
        sys.exit(0)

    # Logging mínimo para processar args antes de carregar config completo
    if args.debug:
        configure_logging(level="DEBUG")

    app = VoiceProgrammer(config_path=args.config)

    if args.model:
        app._cfg.set(args.model, "transcription", "model")

    if args.debug:
        app._cfg.set("DEBUG", "logging", "level")

    app.run()


if __name__ == "__main__":
    main()
