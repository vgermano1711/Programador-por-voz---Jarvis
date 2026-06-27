"""
Classe base abstrata para engines de TTS.

Decisão de arquitetura: interface unificada permite trocar Coqui ↔ ElevenLabs
via config sem mudar nenhuma outra parte do código. O método speak() é
síncrono por padrão mas a implementação real roda em thread separada
gerenciada pelo player.py, para não bloquear o loop de voz.
"""

from abc import ABC, abstractmethod
from typing import Optional


class TTSEngine(ABC):
    """Interface comum para todos os engines de síntese de voz."""

    @abstractmethod
    def synthesize(self, text: str) -> bytes:
        """
        Converte texto em áudio PCM ou MP3.
        Retorna bytes crus do áudio para ser tocado pelo player.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Verifica se o engine está disponível (modelo carregado, API acessível etc.)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome identificador do engine."""
