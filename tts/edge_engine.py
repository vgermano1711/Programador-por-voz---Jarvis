"""
TTS engine via Microsoft Edge TTS (edge-tts).

Voz padrão: pt-PT-DuarteNeural
  - Masculina, tom calmo e formal
  - Português europeu — cadência comedida, soa mais sóbrio que pt-BR
  - Sem necessidade de API key, conta ou instalação de modelo
  - Latência ~300-500ms para frases curtas (requer internet)
  - Gratuita via serviço de síntese do Microsoft Edge

Por que pt-PT-DuarteNeural e não pt-BR-AntonioNeural?
  O sotaque europeu tem cadência mais comedida e formal ao ouvido brasileiro,
  aproximando-se do "perfil de assistente britânico formal" sem copiar nenhuma
  voz de personagem ou ator específico. pt-BR-AntonioNeural é mais casual.

Dependências: pip install edge-tts miniaudio
"""

import asyncio
import io
import wave
from typing import Optional

from .base import TTSEngine
from logging_setup import get_logger

logger = get_logger(__name__)


class EdgeTTSEngine(TTSEngine):
    """
    TTS via Microsoft Edge usando a biblioteca edge-tts.
    Retorna bytes WAV 16-bit mono para compatibilidade com AudioPlayer.
    """

    def __init__(
        self,
        voice: str = "pt-PT-DuarteNeural",
        rate: str = "+0%",
        pitch: str = "-5Hz",
    ) -> None:
        self._voice = voice
        self._rate = rate
        self._pitch = pitch
        self._available: Optional[bool] = None

    def synthesize(self, text: str) -> bytes:
        if not text.strip():
            return b""
        try:
            return asyncio.run(self._synthesize_async(text))
        except Exception as exc:
            logger.error("edge-tts falhou: %s", exc)
            return b""

    async def _synthesize_async(self, text: str) -> bytes:
        import edge_tts  # noqa: importado aqui para lazy-load
        communicate = edge_tts.Communicate(text, self._voice, rate=self._rate, pitch=self._pitch)
        mp3_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_chunks.append(chunk["data"])
        if not mp3_chunks:
            return b""
        return self._mp3_to_wav(b"".join(mp3_chunks))

    def _mp3_to_wav(self, mp3_bytes: bytes) -> bytes:
        """Converte MP3 para WAV 16-bit mono usando miniaudio (sem ffmpeg)."""
        try:
            import miniaudio
            decoded = miniaudio.decode(
                mp3_bytes,
                nchannels=1,
                sample_rate=24000,
                output_format=miniaudio.SampleFormat.SIGNED16,
            )
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(decoded.nchannels)
                wf.setsampwidth(2)  # int16 = 2 bytes por amostra
                wf.setframerate(decoded.sample_rate)
                wf.writeframes(bytes(decoded.samples))
            buf.seek(0)
            return buf.read()
        except Exception as exc:
            logger.error("Falha ao converter MP3→WAV: %s", exc)
            return b""

    @property
    def name(self) -> str:
        return f"edge-tts ({self._voice})"

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import edge_tts  # noqa
            import miniaudio  # noqa
            self._available = True
        except ImportError as exc:
            logger.warning("edge-tts indisponível: %s — instale: pip install edge-tts miniaudio", exc)
            self._available = False
        return self._available
