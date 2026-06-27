"""
Engine de TTS local usando Coqui TTS (open-source, offline).

Por que Coqui TTS como padrão?
- 100% offline: nenhum dado de voz sai do computador
- Gratuito: sem limites de uso ou API key
- Qualidade razoável em pt-BR com modelo XTTS v2
- Desvantagem: ~1-3s de latência, ~1.8GB de modelo, requer GPU para ser rápido

Instalação:
    pip install TTS
    # Modelo baixado automaticamente na primeira execução (~1.8GB)

Modelos recomendados para pt-BR:
    tts_models/pt/cv/vits           — rápido, qualidade boa (~120MB)
    tts_models/multilingual/multi-dataset/xtts_v2  — qualidade excelente, lento (~1.8GB)
"""

import io
import wave
from typing import Optional

from .base import TTSEngine
from logging_setup import get_logger

logger = get_logger(__name__)

# Modelo leve padrão — qualidade boa para conversas simples
_DEFAULT_MODEL = "tts_models/pt/cv/vits"


class CoquiTTSEngine(TTSEngine):
    """TTS local via Coqui TTS."""

    def __init__(self, model_name: str = _DEFAULT_MODEL, gpu: bool = False) -> None:
        self._model_name = model_name
        self._gpu = gpu
        self._tts = None
        self._load()

    def _load(self) -> None:
        try:
            from TTS.api import TTS
            logger.info("Carregando modelo TTS '%s'... (pode demorar na 1ª execução)", self._model_name)
            self._tts = TTS(model_name=self._model_name, gpu=self._gpu)
            logger.info("Modelo TTS carregado.")
        except ImportError:
            logger.error(
                "Coqui TTS não instalado. Execute: pip install TTS\n"
                "Atenção: requer ~500MB de dependências."
            )
        except Exception as exc:
            logger.error("Falha ao carregar Coqui TTS: %s", exc)

    def synthesize(self, text: str) -> bytes:
        """Retorna bytes WAV do texto sintetizado."""
        if not self._tts:
            raise RuntimeError("Modelo TTS não carregado.")

        try:
            # Coqui retorna lista de amostras float
            samples = self._tts.tts(text=text)
            sample_rate = self._tts.synthesizer.output_sample_rate

            # Converte para WAV bytes
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)  # 16-bit
                wav.setframerate(sample_rate)
                import numpy as np
                pcm = (np.array(samples) * 32767).astype(np.int16)
                wav.writeframes(pcm.tobytes())

            return buf.getvalue()

        except Exception as exc:
            logger.error("Erro na síntese Coqui: %s", exc)
            raise

    def is_available(self) -> bool:
        return self._tts is not None

    @property
    def name(self) -> str:
        return f"coqui:{self._model_name}"
