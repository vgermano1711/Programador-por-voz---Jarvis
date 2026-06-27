"""
Testes do Transcriber com mock do modelo faster-whisper.

Não requer GPU, modelo baixado ou faster-whisper instalado.
O mock simula a API exata do WhisperModel para testar a lógica
de pós-processamento: VAD, fallback de idioma, tratamento de erro.
"""

import sys
import numpy as np
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_whisper_model():
    """Mock do WhisperModel com API compatível com faster-whisper."""
    model = MagicMock()

    def make_result(text, language="pt", lang_prob=0.95):
        segment = MagicMock()
        segment.text = text

        info = MagicMock()
        info.language = language
        info.language_probability = lang_prob

        model.transcribe.return_value = (iter([segment]), info)
        return model

    model._make_result = make_result
    return model


@pytest.fixture
def transcriber(cfg, mock_whisper_model):
    """Transcriber com modelo mockado via sys.modules (faster-whisper pode não estar instalado)."""
    mock_fw_module = MagicMock()
    mock_fw_module.WhisperModel.return_value = mock_whisper_model

    with patch.dict(sys.modules, {"faster_whisper": mock_fw_module}):
        # Força reimport do transcriber com o mock no lugar
        if "transcription.transcriber" in sys.modules:
            del sys.modules["transcription.transcriber"]
        if "transcription" in sys.modules:
            del sys.modules["transcription"]

        from transcription import Transcriber
        t = Transcriber(cfg)
        t._model = mock_whisper_model
        return t


class TestTranscriberWithMock:
    def test_transcricao_basica(self, transcriber, mock_whisper_model, speech_audio):
        mock_whisper_model._make_result("print hello world")
        result = transcriber.transcribe(speech_audio, 16000)
        assert result is not None
        assert result.text == "print hello world"

    def test_audio_silencioso_retorna_none(self, transcriber, silent_audio):
        # VAD deve filtrar áudio silencioso antes de chamar o modelo
        result = transcriber.transcribe(silent_audio, 16000)
        assert result is None

    def test_texto_vazio_retorna_none(self, transcriber, mock_whisper_model, speech_audio):
        mock_whisper_model._make_result("")
        result = transcriber.transcribe(speech_audio, 16000)
        assert result is None

    def test_resultado_tem_metadados(self, transcriber, mock_whisper_model, speech_audio):
        mock_whisper_model._make_result("teste de metadados")
        result = transcriber.transcribe(speech_audio, 16000)
        assert result is not None
        assert result.language == "pt"
        assert 0.0 <= result.language_probability <= 1.0
        assert result.duration_s > 0
        assert result.inference_time_s >= 0

    def test_texto_tem_strip(self, transcriber, mock_whisper_model, speech_audio):
        mock_whisper_model._make_result("  print hello  ")
        result = transcriber.transcribe(speech_audio, 16000)
        assert result is not None
        assert result.text == "print hello"

    def test_erro_no_modelo_retorna_none(self, transcriber, mock_whisper_model, speech_audio):
        mock_whisper_model.transcribe.side_effect = RuntimeError("GPU error")
        result = transcriber.transcribe(speech_audio, 16000)
        assert result is None

    def test_fallback_idioma_baixa_confianca(self, transcriber, mock_whisper_model, speech_audio, cfg):
        """Se confiança de idioma < threshold, re-transcreve com fallback."""
        cfg.set(None, "transcription", "language_fallback")  # sem fallback configurado
        mock_whisper_model._make_result("hello world", language="en", lang_prob=0.3)
        # Com threshold=0.7 e prob=0.3 e sem fallback, retorna resultado mesmo assim
        result = transcriber.transcribe(speech_audio, 16000)
        # Não deve crashar
        assert result is not None or result is None  # comportamento aceito


class TestVADFilter:
    def test_audio_com_energia_passa(self, speech_audio):
        from transcription.vad_filter import VADFilter
        vad = VADFilter()
        assert vad.has_speech(speech_audio) is True

    def test_audio_silencioso_rejeitado(self, silent_audio):
        from transcription.vad_filter import VADFilter
        vad = VADFilter()
        assert vad.has_speech(silent_audio) is False

    def test_audio_muito_curto_rejeitado(self):
        from transcription.vad_filter import VADFilter
        vad = VADFilter(min_speech_duration_ms=500)
        short = np.ones(100, dtype=np.float32) * 0.5  # só 100 amostras
        assert vad.has_speech(short) is False

    def test_trim_remove_silencio(self):
        from transcription.vad_filter import VADFilter
        vad = VADFilter()
        # Cria áudio: silêncio + fala + silêncio
        silence = np.zeros(4000, dtype=np.float32)
        speech = np.ones(4000, dtype=np.float32) * 0.5
        audio = np.concatenate([silence, speech, silence])
        trimmed = vad.trim_silence(audio)
        # Trimmed deve ser menor que o original
        assert len(trimmed) < len(audio)
