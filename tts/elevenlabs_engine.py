"""
Engine de TTS cloud usando ElevenLabs API.

Por que ElevenLabs como alternativa premium?
- Voz mais natural e humanizada que qualquer modelo local
- Latência baixa via streaming (~300ms para primeiros chunks)
- Suporte nativo a pt-BR com vozes de alta qualidade
- Desvantagem: pago além do free tier (~10k chars/mês grátis), requer internet,
  áudio de voz sai do computador para servidores da ElevenLabs

A API key é lida via keyring (nunca hardcoded). Se não configurada, o engine
não inicializa e registra aviso claro.

Configurar key:
    python -c "from audit.credentials import set_credential; set_credential('elevenlabs', 'SUA_KEY')"
    # ou via variável de ambiente: ELEVENLABS_API_KEY=...
"""

import io
import os
from typing import Optional

from .base import TTSEngine
from logging_setup import get_logger

logger = get_logger(__name__)

_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

# Voz padrão: Rachel (en) — substitua por uma voz pt-BR da sua conta
_DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
_DEFAULT_MODEL_ID = "eleven_multilingual_v2"


class ElevenLabsEngine(TTSEngine):
    """TTS cloud via ElevenLabs REST API com streaming."""

    def __init__(
        self,
        voice_id: str = _DEFAULT_VOICE_ID,
        model_id: str = _DEFAULT_MODEL_ID,
    ) -> None:
        self._voice_id = voice_id
        self._model_id = model_id
        self._api_key: Optional[str] = self._load_api_key()

    def _load_api_key(self) -> Optional[str]:
        """Carrega API key de variável de ambiente ou keyring."""
        key = os.environ.get("ELEVENLABS_API_KEY")
        if key:
            return key

        try:
            from audit.credentials import get_credential
            key = get_credential("elevenlabs")
            if key:
                return key
        except Exception:
            pass

        logger.warning(
            "ElevenLabs API key não configurada.\n"
            "Configure via: export ELEVENLABS_API_KEY=sua_key\n"
            "Ou via keyring: python -c \"from audit.credentials import set_credential; "
            "set_credential('elevenlabs', 'SUA_KEY')\""
        )
        return None

    def synthesize(self, text: str) -> bytes:
        """Chama ElevenLabs API e retorna bytes MP3."""
        if not self._api_key:
            raise RuntimeError("ElevenLabs API key não configurada.")

        try:
            import urllib.request
            import json

            url = _API_URL.format(voice_id=self._voice_id)
            payload = json.dumps({
                "text": text,
                "model_id": self._model_id,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.3,
                    "use_speaker_boost": True,
                },
            }).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "xi-api-key": self._api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                audio_bytes = resp.read()

            logger.debug("ElevenLabs sintetizou %d bytes para %d chars.", len(audio_bytes), len(text))
            return audio_bytes

        except Exception as exc:
            logger.error("Erro na síntese ElevenLabs: %s", exc)
            raise

    def is_available(self) -> bool:
        return self._api_key is not None

    @property
    def name(self) -> str:
        return f"elevenlabs:{self._voice_id}"
