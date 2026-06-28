from typing import Any

from logging_setup import get_logger

logger = get_logger(__name__)

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False
    logger.warning("numpy não instalado — EmotionDetector retornará estado padrão.")

try:
    from scipy import signal as _scipy_signal
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False

_STATE_CALM = "calm"
_STATE_STRESSED = "stressed"
_STATE_EXCITED = "excited"
_STATE_TIRED = "tired"

_TONE_MODIFIERS: dict[str, str] = {
    _STATE_STRESSED: "Victor parece estressado. Seja mais direto e tranquilizador.",
    _STATE_EXCITED: "Victor está animado. Combine a energia.",
    _STATE_TIRED: "Victor parece cansado. Seja especialmente conciso.",
    _STATE_CALM: "",
}


class EmotionDetector:
    """
    Detecta estado emocional aproximado a partir de áudio mono float32,
    usando heurísticas baseadas em RMS, zero-crossing rate e variação de energia.
    """

    def detect(self, audio: "np.ndarray", sample_rate: int) -> dict[str, Any]:
        if not _NUMPY_AVAILABLE:
            return {"state": _STATE_CALM, "confidence": 0.0, "metrics": {}}

        if len(audio) == 0:
            return {"state": _STATE_CALM, "confidence": 0.0, "metrics": {}}

        rms = float(np.sqrt(np.mean(audio ** 2)))
        zcr = self._zero_crossing_rate(audio)
        energy_variation = self._energy_variation(audio, sample_rate)

        state, confidence = self._classify(rms, zcr, energy_variation)

        return {
            "state": state,
            "confidence": round(confidence, 3),
            "metrics": {
                "rms": round(rms, 5),
                "zcr": round(zcr, 5),
                "energy_variation": round(energy_variation, 5),
            },
        }

    def get_tone_modifier(self, state: str) -> str:
        return _TONE_MODIFIERS.get(state, "")

    def _zero_crossing_rate(self, audio: "np.ndarray") -> float:
        signs = np.sign(audio)
        crossings = np.sum(np.diff(signs) != 0)
        return float(crossings) / max(len(audio) - 1, 1)

    def _energy_variation(self, audio: "np.ndarray", sample_rate: int) -> float:
        frame_size = max(1, sample_rate // 100)
        n_frames = len(audio) // frame_size
        if n_frames < 2:
            return 0.0
        frames = audio[: n_frames * frame_size].reshape(n_frames, frame_size)
        frame_energies = np.sqrt(np.mean(frames ** 2, axis=1))
        mean_energy = np.mean(frame_energies)
        if mean_energy < 1e-10:
            return 0.0
        return float(np.std(frame_energies) / mean_energy)

    def _classify(self, rms: float, zcr: float, variation: float) -> tuple[str, float]:
        high_energy = rms > 0.05
        low_energy = rms < 0.01
        high_zcr = zcr > 0.10
        high_variation = variation > 0.50

        if high_energy and high_variation and high_zcr:
            confidence = min(1.0, rms * 10 + variation + zcr * 5)
            return _STATE_STRESSED, min(1.0, confidence / 3.0)

        if high_energy and not high_variation and high_zcr:
            confidence = min(1.0, rms * 10 + zcr * 5)
            return _STATE_EXCITED, min(1.0, confidence / 2.0)

        if low_energy and not high_variation:
            confidence = min(1.0, (0.01 - rms) * 200 + 0.4)
            return _STATE_TIRED, min(1.0, confidence)

        confidence = 0.5
        return _STATE_CALM, confidence
