"""
Reproduz áudio sintetizado pelo TTS com suporte a interrupção imediata.

Estratégia: sounddevice.OutputStream em thread daemon. O threading.Event
_stop_event permite interrupção instantânea sem esperar o buffer esvaziar.
Isso implementa o requisito "para de falar" via comando de voz ou hotkey.

Por que sounddevice e não pygame/playsound?
- sounddevice já é dependência do módulo de captura (reutiliza a mesma lib)
- Controle fino de streaming — podemos parar sample-by-sample
- Sem dependências de sistema de áudio extra (SDL, etc.)
"""

import io
import threading
from typing import Optional

import numpy as np

from logging_setup import get_logger

logger = get_logger(__name__)


class AudioPlayer:
    """
    Toca bytes de áudio WAV/PCM em thread separada.
    Pode ser interrompido a qualquer momento via stop().
    """

    def __init__(self, sample_rate: int = 22050, channels: int = 1) -> None:
        self._sample_rate = sample_rate
        self._channels = channels
        self._stop_event = threading.Event()
        self._done_event = threading.Event()
        self._done_event.set()  # começa "done" (nada tocando)
        self._play_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def play(self, audio_bytes: bytes, sample_rate: Optional[int] = None) -> None:
        """
        Toca áudio em thread separada. Se já houver áudio tocando, para e
        substitui pelo novo (comportamento "interrompe e recomeça").
        """
        self.stop()  # para qualquer áudio em andamento

        rate = sample_rate or self._sample_rate
        self._stop_event.clear()
        self._done_event.clear()

        self._play_thread = threading.Thread(
            target=self._play_wav,
            args=(audio_bytes, rate),
            daemon=True,
            name="tts-player",
        )
        self._play_thread.start()

    def stop(self) -> None:
        """Para o áudio imediatamente."""
        self._stop_event.set()
        if self._play_thread and self._play_thread.is_alive():
            self._play_thread.join(timeout=0.5)
        self._done_event.set()

    def wait(self, timeout: Optional[float] = None) -> None:
        """Bloqueia até o áudio atual terminar (ou timeout em segundos)."""
        self._done_event.wait(timeout=timeout)

    def is_playing(self) -> bool:
        return self._play_thread is not None and self._play_thread.is_alive()

    def _play_wav(self, audio_bytes: bytes, sample_rate: int) -> None:
        try:
            import sounddevice as sd

            audio_array = self._decode_audio(audio_bytes)
            if audio_array is None:
                return

            chunk_size = int(sample_rate * 0.05)  # chunks de 50ms
            total = len(audio_array)
            pos = 0

            with sd.OutputStream(
                samplerate=sample_rate,
                channels=self._channels,
                dtype="float32",
            ) as stream:
                while pos < total and not self._stop_event.is_set():
                    end = min(pos + chunk_size, total)
                    chunk = audio_array[pos:end]
                    if self._channels == 1 and chunk.ndim == 1:
                        chunk = chunk.reshape(-1, 1)
                    stream.write(chunk)
                    pos = end

            logger.debug("Reprodução de áudio concluída.")

        except Exception as exc:
            logger.error("Erro na reprodução de áudio: %s", exc)
        finally:
            self._done_event.set()

    def _decode_audio(self, audio_bytes: bytes) -> Optional[np.ndarray]:
        """Decodifica WAV bytes para numpy float32."""
        try:
            import wave
            import struct

            with wave.open(io.BytesIO(audio_bytes)) as wav:
                n_frames = wav.getnframes()
                n_channels = wav.getnchannels()
                sampwidth = wav.getsampwidth()
                raw = wav.readframes(n_frames)

            # Converte bytes para numpy
            dtype_map = {1: np.int8, 2: np.int16, 4: np.int32}
            dtype = dtype_map.get(sampwidth, np.int16)
            audio = np.frombuffer(raw, dtype=dtype).astype(np.float32)
            audio /= np.iinfo(dtype).max  # normaliza para [-1, 1]

            if n_channels > 1:
                audio = audio.reshape(-1, n_channels).mean(axis=1)  # mono

            return audio

        except Exception:
            # Tenta como float32 raw (Coqui retorna assim às vezes)
            try:
                return np.frombuffer(audio_bytes, dtype=np.float32)
            except Exception as exc:
                logger.error("Falha ao decodificar áudio: %s", exc)
                return None
