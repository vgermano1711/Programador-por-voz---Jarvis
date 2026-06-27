"""
Wrapper sobre faster-whisper para transcrição de fala em português.

Por que faster-whisper e não whisper original da OpenAI?
- 4× mais rápido que whisper-python no mesmo hardware (CTranslate2 + quantização int8).
- Menor uso de memória (int8 vs float32).
- Streaming de segmentos: pode exibir palavras parciais enquanto processa.
- API compatível: troca direta se necessário.

Modelo padrão: "small"
- 244M parâmetros, ~2s de latência no CPU para 5s de áudio.
- WER (Word Error Rate) em português: ~8-12% — adequado para comandos técnicos.
- "base" é mais rápido mas erra mais em jargão; "medium" é mais preciso mas ~2× mais lento.
"""

import time
from typing import Optional

import numpy as np

from logging_setup import get_logger
from .vad_filter import VADFilter

logger = get_logger(__name__)


class TranscriptionResult:
    """Resultado de uma transcrição com metadados de confiança."""

    def __init__(
        self,
        text: str,
        language: str,
        language_probability: float,
        duration_s: float,
        inference_time_s: float,
    ) -> None:
        self.text = text.strip()
        self.language = language
        self.language_probability = language_probability
        self.duration_s = duration_s
        self.inference_time_s = inference_time_s

    def __repr__(self) -> str:
        return (
            f"TranscriptionResult(text={self.text!r}, lang={self.language}, "
            f"prob={self.language_probability:.2f}, rtf={self.inference_time_s/max(self.duration_s,0.001):.2f}x)"
        )


class Transcriber:
    """
    Gerencia o modelo faster-whisper e processa áudio para texto.

    O modelo é carregado uma única vez na inicialização (load lazy via first_use=True
    não é usado aqui, pois queremos falhar rápido se o modelo não estiver disponível).
    """

    def __init__(self, cfg) -> None:
        self._model_size: str = cfg.get("transcription", "model", default="small")
        self._device: str = cfg.get("transcription", "device", default="cpu")
        self._compute_type: str = cfg.get("transcription", "compute_type", default="int8")
        self._language: Optional[str] = cfg.get("transcription", "language", default="pt")
        self._language_fallback: Optional[str] = cfg.get("transcription", "language_fallback")
        self._lang_confidence_threshold: float = cfg.get(
            "transcription", "language_confidence_threshold", default=0.7
        )
        self._beam_size: int = cfg.get("transcription", "beam_size", default=5)
        self._initial_prompt: str = cfg.get(
            "transcription", "initial_prompt",
            default="Código Python, terminal, programação em português."
        )

        vad_cfg = cfg.get("vad") or {}
        self._vad = VADFilter(
            min_speech_duration_ms=vad_cfg.get("min_speech_duration_ms", 300),
            sample_rate=16000,
        ) if cfg.get("vad", "enabled", default=True) else None

        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        """Carrega o modelo Whisper. Pode demorar alguns segundos na primeira execução."""
        try:
            from faster_whisper import WhisperModel

            logger.info(
                "Carregando modelo Whisper '%s' no device=%s compute_type=%s...",
                self._model_size, self._device, self._compute_type
            )
            t0 = time.time()
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
            )
            logger.info("Modelo carregado em %.1fs", time.time() - t0)

        except ImportError:
            logger.error(
                "faster-whisper não instalado. Execute: pip install faster-whisper"
            )
            raise
        except Exception as exc:
            logger.error("Falha ao carregar modelo Whisper '%s': %s", self._model_size, exc)
            raise

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> Optional[TranscriptionResult]:
        """
        Transcreve áudio numpy float32 mono para texto.

        Retorna None se: áudio sem fala, transcrição vazia, ou erro.
        """
        if self._model is None:
            logger.error("Modelo não carregado.")
            return None

        # Pré-filtragem VAD
        if self._vad and not self._vad.has_speech(audio):
            logger.info("VAD: áudio descartado (sem fala detectada).")
            return None

        if self._vad:
            audio = self._vad.trim_silence(audio)

        duration_s = len(audio) / sample_rate
        if duration_s < 0.3:
            logger.debug("Áudio muito curto após trim: %.2fs", duration_s)
            return None

        try:
            t0 = time.time()
            segments, info = self._model.transcribe(
                audio,
                language=self._language,
                beam_size=self._beam_size,
                initial_prompt=self._initial_prompt,
                vad_filter=True,          # VAD interno do faster-whisper (silero)
                vad_parameters={
                    "min_silence_duration_ms": 500,
                    "speech_pad_ms": 100,
                },
            )

            text = " ".join(seg.text for seg in segments).strip()
            inference_time = time.time() - t0

            if not text:
                logger.info("Transcrição vazia (silêncio ou ruído).")
                return None

            # Fallback de idioma: se confiança baixa, re-transcreve sem forçar idioma
            detected_lang_prob = info.language_probability
            if (
                self._language
                and detected_lang_prob < self._lang_confidence_threshold
                and self._language_fallback is not None
            ):
                logger.warning(
                    "Confiança de idioma baixa (%.2f < %.2f). Re-transcrevendo com fallback.",
                    detected_lang_prob, self._lang_confidence_threshold
                )
                return self._transcribe_with_fallback(audio, sample_rate, duration_s)

            result = TranscriptionResult(
                text=text,
                language=info.language,
                language_probability=detected_lang_prob,
                duration_s=duration_s,
                inference_time_s=inference_time,
            )
            logger.info("Transcrito: %r [%.2fs, RTF=%.2f]", text, inference_time, inference_time/duration_s)
            return result

        except Exception as exc:
            logger.error("Erro durante transcrição: %s", exc, exc_info=True)
            return None

    def _transcribe_with_fallback(
        self, audio: np.ndarray, sample_rate: int, duration_s: float
    ) -> Optional[TranscriptionResult]:
        """Re-transcreve sem forçar idioma (detecção automática)."""
        try:
            t0 = time.time()
            segments, info = self._model.transcribe(
                audio,
                language=None,  # detecção automática
                beam_size=self._beam_size,
            )
            text = " ".join(seg.text for seg in segments).strip()
            return TranscriptionResult(
                text=text,
                language=info.language,
                language_probability=info.language_probability,
                duration_s=duration_s,
                inference_time_s=time.time() - t0,
            ) if text else None
        except Exception as exc:
            logger.error("Erro no fallback de transcrição: %s", exc)
            return None
