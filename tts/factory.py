"""Factory que instancia o engine de TTS correto com base na configuração."""

from .base import TTSEngine
from logging_setup import get_logger

logger = get_logger(__name__)


def create_tts_engine(cfg) -> TTSEngine:
    """
    Cria e retorna o engine de TTS configurado.

    Config relevante (tts section):
        engine: "edge" | "elevenlabs" | "coqui"
        edge_voice: str (ex: "pt-PT-DuarteNeural")
        edge_rate: str (ex: "+0%")
        edge_pitch: str (ex: "-5Hz")
        elevenlabs_voice_id: str
        elevenlabs_model_id: str
        coqui_model: str
        coqui_gpu: bool
    """
    engine_name = cfg.get("tts", "engine", default="edge")

    if engine_name == "edge":
        from .edge_engine import EdgeTTSEngine
        voice = cfg.get("tts", "edge_voice", default="pt-PT-DuarteNeural")
        rate = cfg.get("tts", "edge_rate", default="+0%")
        pitch = cfg.get("tts", "edge_pitch", default="-5Hz")
        engine = EdgeTTSEngine(voice=voice, rate=rate, pitch=pitch)
        if engine.is_available():
            return engine
        logger.warning("edge-tts não disponível. Caindo para Coqui TTS.")
        return _make_coqui(cfg)

    if engine_name == "elevenlabs":
        from .elevenlabs_engine import ElevenLabsEngine
        voice_id = cfg.get("tts", "elevenlabs_voice_id", default="21m00Tcm4TlvDq8ikWAM")
        model_id = cfg.get("tts", "elevenlabs_model_id", default="eleven_multilingual_v2")
        engine = ElevenLabsEngine(voice_id=voice_id, model_id=model_id)
        if engine.is_available():
            return engine
        logger.warning("ElevenLabs não disponível. Caindo para edge-tts.")
        from .edge_engine import EdgeTTSEngine
        return EdgeTTSEngine()

    return _make_coqui(cfg)


def _make_coqui(cfg) -> "TTSEngine":
    from .coqui_engine import CoquiTTSEngine
    model = cfg.get("tts", "coqui_model", default="tts_models/pt/cv/vits")
    gpu = cfg.get("tts", "coqui_gpu", default=False)
    return CoquiTTSEngine(model_name=model, gpu=gpu)
