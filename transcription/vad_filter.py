"""
Filtro de Voice Activity Detection (VAD) baseado em energia de sinal.

Decisão de arquitetura: implementamos VAD simples baseado em RMS (Root Mean Square)
em vez de usar webrtcvad ou silero-vad, para evitar dependências pesadas e latência
adicional. O faster-whisper já tem VAD interno (via silero) que é ativado via
parâmetro; este filtro é uma pré-filtragem rápida antes de chamar o modelo.

Para VAD mais robusto em ambientes ruidosos, considere silero-vad:
    pip install silero-vad
"""

import numpy as np

from logging_setup import get_logger

logger = get_logger(__name__)


class VADFilter:
    """Descarta áudios que não contêm fala detectável."""

    def __init__(
        self,
        min_speech_duration_ms: int = 300,
        sample_rate: int = 16000,
        energy_threshold: float = 0.01,
    ) -> None:
        self._min_samples = int(min_speech_duration_ms * sample_rate / 1000)
        self._threshold = energy_threshold

    def has_speech(self, audio: np.ndarray) -> bool:
        """
        Retorna True se o áudio contém fala acima do threshold de energia.

        O threshold de 0.01 (RMS normalizado) filtra silêncio e ruído ambiente leve,
        mas pode precisar de ajuste em ambientes muito ruidosos.
        """
        if len(audio) < self._min_samples:
            logger.debug(
                "Áudio muito curto: %d amostras < %d mínimo",
                len(audio), self._min_samples,
            )
            return False

        rms = float(np.sqrt(np.mean(audio ** 2)))
        has_energy = rms > self._threshold

        logger.debug("VAD: RMS=%.4f, threshold=%.4f, tem_fala=%s", rms, self._threshold, has_energy)
        return has_energy

    def trim_silence(self, audio: np.ndarray, margin_ms: int = 100) -> np.ndarray:
        """Remove silêncio do início e fim, mantendo margem para o Whisper."""
        margin_samples = int(margin_ms * 16000 / 1000)
        # Energia por janela de 10ms
        window = 160
        energy = [
            np.sqrt(np.mean(audio[i:i+window] ** 2))
            for i in range(0, len(audio) - window, window)
        ]
        if not energy:
            return audio

        start_idx = 0
        end_idx = len(energy) - 1

        for i, e in enumerate(energy):
            if e > self._threshold:
                start_idx = max(0, i - 1)
                break

        for i in range(len(energy) - 1, -1, -1):
            if energy[i] > self._threshold:
                end_idx = min(len(energy) - 1, i + 1)
                break

        start_sample = max(0, start_idx * window - margin_samples)
        end_sample = min(len(audio), (end_idx + 1) * window + margin_samples)
        return audio[start_sample:end_sample]
