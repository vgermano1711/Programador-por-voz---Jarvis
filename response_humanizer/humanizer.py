"""
Humanizador de respostas do Claude Code para leitura em voz alta.

Problema: o Claude Code responde com blocos de código, markdown, listas,
tabelas ASCII — tudo adequado para leitura visual mas péssimo para TTS.
Um leitor que encontra "```python\ndef foo():\n    return 42```" vai falar
"acento grave acento grave acento grave python def foo dois pontos return
quarenta e dois acento grave acento grave acento grave" — absolutamente inútil.

Estratégia aplicada (em ordem):
1. Remove blocos de código completos, substituindo por aviso verbal.
2. Remove formatação Markdown inline (**, *, `, #, etc.)
3. Colapsa listas em frases naturais.
4. Normaliza pontuação e abreviações para TTS.
5. Trunca se ainda muito longo (max_chars configurable), adicionando aviso verbal.
6. Divide em sentenças para TTS progressivo (futuro).
"""

import re
from typing import Optional

from logging_setup import get_logger

logger = get_logger(__name__)

# Aviso falado quando bloco de código é removido
_CODE_NOTICE = "O código completo está no terminal."

# Limite de caracteres antes de truncar para fala (aprox. 45s de fala)
_DEFAULT_MAX_CHARS = 800


class Humanizer:
    """Converte resposta markdown do Claude em texto natural para TTS."""

    def __init__(self, cfg=None) -> None:
        self._max_chars: int = _DEFAULT_MAX_CHARS
        self._code_notice: str = _CODE_NOTICE
        self._announce_code: bool = True

        if cfg:
            self._max_chars = cfg.get("tts", "humanizer_max_chars", default=_DEFAULT_MAX_CHARS)
            self._announce_code = cfg.get("tts", "humanizer_announce_code", default=True)

    def humanize(self, text: str) -> str:
        """
        Processa texto markdown e retorna versão adequada para fala.
        Retorna string vazia se o texto não tiver conteúdo falável.
        """
        if not text or not text.strip():
            return ""

        original_len = len(text)
        result = text

        # 1. Remove blocos de código (```...```)
        has_code = bool(re.search(r"```[\s\S]*?```", result, re.MULTILINE))
        result = re.sub(r"```[\s\S]*?```", "", result, flags=re.MULTILINE)

        # Remove code inline: `algo`
        result = re.sub(r"`[^`\n]+`", lambda m: self._inline_code(m.group()), result)

        # 2. Remove cabeçalhos Markdown (### Título → "Título")
        result = re.sub(r"^#{1,6}\s+(.+)$", r"\1.", result, flags=re.MULTILINE)

        # 3. Remove bold/italic (**texto**, *texto*, __texto__, _texto_)
        result = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", result)
        result = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", result)

        # 4. Remove links Markdown ([texto](url) → texto)
        result = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", result)

        # 5. Converte listas em frases (- item → "item,")
        result = re.sub(r"^\s*[-*+]\s+(.+)$", r"\1,", result, flags=re.MULTILINE)
        result = re.sub(r"^\s*\d+\.\s+(.+)$", r"\1,", result, flags=re.MULTILINE)

        # 6. Remove linhas horizontais (--- ou ***)
        result = re.sub(r"^[-*_]{3,}$", "", result, flags=re.MULTILINE)

        # 7. Normaliza espaço em branco
        result = re.sub(r"\n{3,}", "\n\n", result)
        result = re.sub(r"[ \t]+", " ", result)
        result = result.strip()

        # 8. Substitui abreviações comuns
        result = self._expand_abbreviations(result)

        # 9. Adiciona aviso de código se removeu blocos
        if has_code and self._announce_code and result:
            result = result.rstrip() + " " + self._code_notice
        elif has_code and not result:
            result = self._code_notice

        # 10. Trunca se muito longo
        if len(result) > self._max_chars:
            truncated = result[:self._max_chars]
            # Tenta truncar em fim de frase para não cortar no meio
            last_sentence = max(
                truncated.rfind(". "),
                truncated.rfind("! "),
                truncated.rfind("? "),
            )
            if last_sentence > self._max_chars * 0.6:
                truncated = truncated[:last_sentence + 1]
            result = truncated + " A resposta completa está no terminal."

            logger.debug(
                "Resposta truncada: %d → %d chars para TTS.", original_len, len(result)
            )

        logger.debug("Humanizer: %d → %d chars.", original_len, len(result))
        return result.strip()

    def _inline_code(self, code: str) -> str:
        """Remove backticks mas mantém o conteúdo se for curto e legível."""
        inner = code.strip("`").strip()
        # Se contém apenas letras/números/underscores e é curto, lê normalmente
        if re.match(r"^[\w\s]{1,30}$", inner):
            return inner
        return ""  # código técnico longo: silencia

    def _expand_abbreviations(self, text: str) -> str:
        """Expande abreviações comuns para que o TTS pronuncie corretamente."""
        replacements = {
            r"\bAPI\b": "a pê í",
            r"\bCLI\b": "sê ê lê í",
            r"\bCPU\b": "sê pê u",
            r"\bGPU\b": "gê pê u",
            r"\bJSON\b": "jésón",
            r"\bYAML\b": "iâml",
            r"\bSQL\b": "ésse quê êl",
            r"\bURL\b": "u erre éle",
            r"\bHTTP\b": "agá tê tê pê",
            r"\bHTTPS\b": "agá tê tê pê ésse",
            r"\bMCP\b": "ême cê pê",
            r"\bTTS\b": "tê tê ésse",
            r"\bSTT\b": "ésse tê tê",
            r"\bVAD\b": "vê a dê",
            r"\bOCR\b": "ó sê erre",
            r"\bpty\b": "pê tê í",
            r"\btmux\b": "tê mux",
            r"\bvenv\b": "vê env",
            r"\bpip\b": "pip",
            r"\bssh\b": "ésse ésse agá",
        }
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    def split_into_sentences(self, text: str) -> list[str]:
        """
        Divide texto humanizado em sentenças para TTS progressivo.
        Permite iniciar a fala antes de sintetizar o texto todo.
        """
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]
