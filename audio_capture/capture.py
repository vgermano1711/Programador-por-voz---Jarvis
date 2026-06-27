"""
Módulo de captura de áudio com suporte a push-to-talk e wake word.

Arquitetura de threading:
- Thread principal: loop de eventos da bandeja/UI
- Thread de captura: sounddevice InputStream bloqueante
- Thread de hotkey: listener pynput em background

O áudio é acumulado em um buffer numpy enquanto a tecla está pressionada.
Ao soltar, o buffer é publicado via callback para o pipeline de transcrição.
"""

import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

from logging_setup import get_logger
from .devices import select_device

logger = get_logger(__name__)

# Tipo do callback: recebe numpy array (float32, mono) e taxa de amostragem
AudioCallback = Callable[[np.ndarray, int], None]


class AudioCapture:
    """
    Gerencia captura de áudio via push-to-talk ou wake word.

    Uso:
        capture = AudioCapture(cfg, on_audio=meu_callback)
        capture.start()
        # ... programa roda ...
        capture.stop()
    """

    def __init__(self, cfg, on_audio: AudioCallback) -> None:
        self._cfg = cfg
        self._on_audio = on_audio

        self._sample_rate: int = cfg.get("audio", "sample_rate", default=16000)
        self._channels: int = cfg.get("audio", "channels", default=1)
        self._max_seconds: int = cfg.get("audio", "max_recording_seconds", default=30)
        self._device_idx: Optional[int] = select_device(
            device_index=cfg.get("audio", "device_index"),
            device_name=cfg.get("audio", "device_name"),
        )
        self._mode: str = cfg.get("activation", "mode", default="push_to_talk")
        self._ptk_key: str = cfg.get("activation", "push_to_talk_key", default="f9")

        self._recording = False
        self._buffer: list[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._hotkey_listener = None
        self._lock = threading.Lock()

        # Status callback para atualizar a bandeja (injetado externamente)
        self.on_status_change: Optional[Callable[[str], None]] = None

    # ── Public API ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Inicia captura de áudio e registra hotkey."""
        self._open_stream()
        if self._mode == "push_to_talk":
            self._start_hotkey_listener()
        elif self._mode == "wake_word":
            self._start_wake_word()
        logger.info("AudioCapture iniciado (modo=%s)", self._mode)

    def stop(self) -> None:
        """Para captura e libera recursos."""
        self._stop_recording()
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if self._hotkey_listener:
            self._hotkey_listener.stop()
        logger.info("AudioCapture encerrado.")

    # ── Stream de áudio ─────────────────────────────────────────────────────────

    def _open_stream(self) -> None:
        try:
            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="float32",
                device=self._device_idx,
                callback=self._audio_callback,
                blocksize=int(self._sample_rate * 0.03),  # chunks de 30ms
            )
            self._stream.start()
            logger.debug("InputStream aberto (rate=%d, device=%s)", self._sample_rate, self._device_idx)
        except sd.PortAudioError as exc:
            logger.error("Falha ao abrir microfone: %s", exc)
            raise

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """Chamado pela thread de áudio do sounddevice a cada chunk."""
        if status:
            logger.warning("Status de áudio: %s", status)
        if self._recording:
            with self._lock:
                self._buffer.append(indata.copy())
                total_seconds = len(self._buffer) * frames / self._sample_rate
                if total_seconds >= self._max_seconds:
                    logger.warning("Gravação interrompida: limite de %ds atingido", self._max_seconds)
                    self._flush_recording()

    # ── Gravação ────────────────────────────────────────────────────────────────

    def _start_recording(self) -> None:
        with self._lock:
            if self._recording:
                return
            self._recording = True
            self._buffer = []
        self._set_status("recording")
        logger.debug("Gravação iniciada.")

    def _stop_recording(self) -> None:
        with self._lock:
            if not self._recording:
                return
            self._recording = False
        self._flush_recording()

    def _flush_recording(self) -> None:
        """Concatena buffer e dispara callback de áudio."""
        with self._lock:
            if not self._buffer:
                logger.debug("Buffer vazio, nada para transcrever.")
                self._set_status("idle")
                return
            audio = np.concatenate(self._buffer, axis=0).flatten()
            self._buffer = []

        self._set_status("processing")
        logger.debug("Áudio capturado: %.2fs", len(audio) / self._sample_rate)
        try:
            self._on_audio(audio, self._sample_rate)
        except Exception as exc:
            logger.error("Erro no callback de áudio: %s", exc)
            self._set_status("error")

    # ── Push-to-talk ────────────────────────────────────────────────────────────

    def _start_hotkey_listener(self) -> None:
        """
        Usa pynput para capturar hotkey globalmente.
        pynput funciona sem root no Linux (via XInput/Wayland) ao contrário
        de `keyboard`, que precisa de /dev/input e root em muitas distros.
        """
        try:
            from pynput import keyboard as kb

            key_name = self._ptk_key.upper()

            # Tenta mapear "F9" → Key.f9, etc.
            try:
                target_key = getattr(kb.Key, key_name.lower())
            except AttributeError:
                # Tecla de caractere comum (ex: "a")
                target_key = kb.KeyCode.from_char(key_name.lower())

            def on_press(key):
                if key == target_key:
                    self._start_recording()

            def on_release(key):
                if key == target_key:
                    self._stop_recording()

            self._hotkey_listener = kb.Listener(
                on_press=on_press, on_release=on_release
            )
            self._hotkey_listener.start()
            logger.info("Push-to-talk ativo na tecla: %s", self._ptk_key)

        except ImportError:
            logger.error(
                "pynput não instalado. Instale com: pip install pynput\n"
                "AVISO: Em Linux, pode ser necessário adicionar seu usuário ao grupo 'input':\n"
                "  sudo usermod -aG input $USER"
            )
            raise
        except Exception as exc:
            logger.error("Falha ao iniciar listener de hotkey: %s", exc)
            raise

    # ── Wake word ───────────────────────────────────────────────────────────────

    def _start_wake_word(self) -> None:
        """
        Inicia detecção de wake word em thread separada.
        Importamos wake_word.py apenas se mode=wake_word para não exigir
        instalação de openwakeword/porcupine quando não necessário.
        """
        from .wake_word import WakeWordDetector

        words = self._cfg.get("activation", "wake_words", default=["claude"])
        engine = self._cfg.get("activation", "wake_word_engine", default="openwakeword")

        detector = WakeWordDetector(
            wake_words=words,
            engine=engine,
            sample_rate=self._sample_rate,
            cfg=self._cfg,
        )

        def _wake_word_loop():
            logger.info("Wake word ativo: %s", words)
            for triggered_word in detector.listen():
                logger.info("Wake word detectada: '%s'", triggered_word)
                self._start_recording()
                # Gravação para automaticamente após silêncio (VAD cuida disso)
                time.sleep(0.5)  # debounce mínimo

        thread = threading.Thread(target=_wake_word_loop, daemon=True, name="wake-word")
        thread.start()

    # ── Utilitários ─────────────────────────────────────────────────────────────

    def _set_status(self, status: str) -> None:
        if self.on_status_change:
            try:
                self.on_status_change(status)
            except Exception:
                pass
