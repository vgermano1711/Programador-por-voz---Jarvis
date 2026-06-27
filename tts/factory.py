"""Factory que instancia o engine de TTS correto com base na configuração."""

from .base import TTSEngine
from logging_setup import get_logger

logger = get_logger(__name__)


def create_tts_engine(cfg) -> TTSEngine:
    """
    Cria e retorna o engine de TTS configurado.

    Config relevante (tts section):
        engine: "coqui" | "elevenlabs"
        coqui_model: nome do modelo Coqui
        coqui_gpu: bool
        elevenlabs_voice_id: str
        elevenlabs_model_id: str
    """
    engine_name = cfg.get("tts", "engine", default="coqui")

    if engine_name == "elevenlabs":
        from .elevenlabs_engine import ElevenLabsEngine
        voice_id = cfg.get("tts", "elevenlabs_voice_id", default="21m00Tcm4TlvDq8ikWAM")
        model_id = cfg.get("tts", "elevenlabs_model_id", default="eleven_multilingual_v2")
        engine = ElevenLabsEngine(voice_id=voice_id, model_id=model_id)
        if not engine.is_available():
            logger.warning("ElevenLabs não disponível. Caindo para Coqui TTS.")
            return _make_coqui(cfg)
        return engine

    return _make_coqui(cfg)


def _make_coqui(cfg) -> "TTSEngine":
    from .coqui_engine import CoquiTTSEngine
    model = cfg.get("tts", "coqui_model", default="tts_models/pt/cv/vits")
    gpu = cfg.get("tts", "coqui_gpu", default=False)
    return CoquiTTSEngine(model_name=model, gpu=gpu)
