"""
Detecção de wake word com suporte a dois engines:

1. openwakeword (padrão):
   - Open-source, gratuito, roda offline.
   - Modelos pré-treinados para "hey mycroft", "alexa", etc.
   - Usamos modelo customizado ou o mais próximo disponível.
   - Trade-off: taxa de falsos positivos ligeiramente maior que Porcupine.

2. Picovoice Porcupine:
   - Alta precisão e baixa latência, especialmente em português.
   - Requer access key gratuita em picovoice.ai (limite de uso no tier free).
   - Melhor escolha se precisão for crítica.

Decisão de padrão: openwakeword, por ser 100% offline e sem API key.
"""

import queue
import threading
from typing import Generator, Optional

import numpy as np

from logging_setup import get_logger

logger = get_logger(__name__)


class WakeWordDetector:
    """
    Detecta wake words no stream de áudio contínuo.
    Funciona como gerador: `for word in detector.listen(): ...`
    """

    def __init__(
        self,
        wake_words: list[str],
        engine: str = "openwakeword",
        sample_rate: int = 16000,
        cfg=None,
    ) -> None:
        self._wake_words = wake_words
        self._engine = engine
        self._sample_rate = sample_rate
        self._cfg = cfg
        self._trigger_queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()

    def listen(self) -> Generator[str, None, None]:
        """Gerador que produz o nome da wake word detectada."""
        if self._engine == "openwakeword":
            thread = threading.Thread(
                target=self._oww_loop, daemon=True, name="oww-detector"
            )
        elif self._engine == "porcupine":
            thread = threading.Thread(
                target=self._porcupine_loop, daemon=True, name="porcupine-detector"
            )
        else:
            raise ValueError(f"Engine de wake word desconhecido: {self._engine}")

        thread.start()

        while not self._stop_event.is_set():
            try:
                word = self._trigger_queue.get(timeout=0.5)
                yield word
            except queue.Empty:
                continue

    def stop(self) -> None:
        self._stop_event.set()

    # ── openwakeword ────────────────────────────────────────────────────────────

    def _oww_loop(self) -> None:
        try:
            import openwakeword
            from openwakeword.model import Model
        except ImportError:
            logger.error(
                "openwakeword não instalado. Execute: pip install openwakeword\n"
                "E baixe os modelos: python -m openwakeword.utils download_models"
            )
            return

        try:
            oww_model = Model(wakeword_models=[], inference_framework="onnx")
        except Exception as exc:
            logger.error("Falha ao carregar openwakeword: %s", exc)
            return

        import sounddevice as sd

        chunk_size = 1280  # 80ms @ 16kHz — recomendado pelo openwakeword

        def audio_cb(indata, frames, time_info, status):
            audio_int16 = (indata[:, 0] * 32767).astype(np.int16)
            predictions = oww_model.predict(audio_int16)
            for model_name, score in predictions.items():
                if score > 0.5:
                    triggered = self._match_wake_word(model_name)
                    if triggered:
                        self._trigger_queue.put(triggered)

        with sd.InputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="float32",
            blocksize=chunk_size,
            callback=audio_cb,
        ):
            self._stop_event.wait()

    def _match_wake_word(self, model_name: str) -> Optional[str]:
        """Verifica se o nome do modelo corresponde a alguma wake word configurada."""
        model_lower = model_name.lower().replace("_", " ")
        for word in self._wake_words:
            if word.lower() in model_lower or model_lower in word.lower():
                return word
        # Fallback: qualquer detecção conta se não temos modelo específico
        return self._wake_words[0] if self._wake_words else None

    # ── Porcupine ───────────────────────────────────────────────────────────────

    def _porcupine_loop(self) -> None:
        try:
            import pvporcupine
        except ImportError:
            logger.error(
                "pvporcupine não instalado. Execute: pip install pvporcupine\n"
                "Obtenha uma access key gratuita em: https://picovoice.ai/"
            )
            return

        access_key = ""
        if self._cfg:
            access_key = self._cfg.get("activation", "porcupine_access_key", default="")

        if not access_key:
            logger.error(
                "Porcupine requer porcupine_access_key em config.yaml.\n"
                "Obtenha gratuitamente em: https://picovoice.ai/"
            )
            return

        try:
            # Mapeamos wake words para keywords do Porcupine
            # "claude" não é palavra nativa, usamos "computer" como aproximação
            # ou modelo customizado .ppn
            keywords = ["computer"]  # placeholder; idealmente usar .ppn customizado
            porcupine = pvporcupine.create(
                access_key=access_key,
                keywords=keywords,
            )
        except Exception as exc:
            logger.error("Falha ao iniciar Porcupine: %s", exc)
            return

        import sounddevice as sd

        frame_length = porcupine.frame_length

        def audio_cb(indata, frames, time_info, status):
            pcm = (indata[:frame_length, 0] * 32767).astype(np.int16).tolist()
            index = porcupine.process(pcm)
            if index >= 0:
                self._trigger_queue.put(self._wake_words[0])

        with sd.InputStream(
            samplerate=porcupine.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=frame_length,
            callback=audio_cb,
        ):
            self._stop_event.wait()

        porcupine.delete()
