"""
Camada de interpretação: diferencia ditado literal de comandos de controle.

Algoritmo de matching:
1. Normaliza o texto (lowercase, remove pontuação, strip).
2. Para cada comando de controle configurado, verifica se alguma frase-gatilho
   está contida no início do texto normalizado (ou é o texto completo).
3. Se match: retorna ControlCommand com o tipo correspondente.
4. Caso contrário: retorna o texto como DICTATION.

Escolhemos matching exato (com normalização) em vez de fuzzy matching para
evitar falsos positivos acidentais durante ditado de código.
"""

import re
import unicodedata
from typing import Optional, Union

from logging_setup import get_logger
from .control_commands import CommandType, ControlCommand, HANDLERS

logger = get_logger(__name__)


def _normalize(text: str) -> str:
    """Remove acentos, pontuação e converte para minúsculas."""
    # Remove acentos (NFD decompõe, filtramos Mn = combining characters)
    nfd = unicodedata.normalize("NFD", text)
    without_accents = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    # Remove pontuação mantendo espaços
    no_punct = re.sub(r"[^\w\s]", "", without_accents)
    return no_punct.lower().strip()


# Mapa de string normalizada → CommandType (preenchido dinamicamente)
_PHRASE_TO_TYPE: dict[str, CommandType] = {
    # built-in fallbacks — sobrescritos pelo Config em tempo de execução
    "cancela": CommandType.CANCELA,
    "cancelar": CommandType.CANCELA,
    "cancela isso": CommandType.CANCELA,
    "interrompe": CommandType.INTERROMPE,
    "interromper": CommandType.INTERROMPE,
    "ctrl c": CommandType.INTERROMPE,
    "para tudo": CommandType.INTERROMPE,
    "repete": CommandType.REPETE,
    "repetir": CommandType.REPETE,
    "repete isso": CommandType.REPETE,
    "repete o ultimo": CommandType.REPETE,
    "limpa tela": CommandType.LIMPA_TELA,
    "limpar tela": CommandType.LIMPA_TELA,
    "limpa o terminal": CommandType.LIMPA_TELA,
    "para": CommandType.PARA,
    "parar": CommandType.PARA,
}

_TYPE_MAP: dict[str, CommandType] = {
    "cancela": CommandType.CANCELA,
    "interrompe": CommandType.INTERROMPE,
    "repete": CommandType.REPETE,
    "limpa_tela": CommandType.LIMPA_TELA,
    "para": CommandType.PARA,
}


class CommandInterpreter:
    """
    Interpreta texto transcrito e classifica como ditado ou comando de controle.

    Carrega frases-gatilho customizáveis da configuração.
    """

    def __init__(self, cfg) -> None:
        self._phrase_map: dict[str, CommandType] = dict(_PHRASE_TO_TYPE)
        self._load_custom_commands(cfg)
        self._last_dictation: Optional[str] = None

    def _load_custom_commands(self, cfg) -> None:
        """Carrega frases de controle do arquivo de configuração."""
        commands_cfg = cfg.get("control_commands") or {}
        for cmd_name, phrases in commands_cfg.items():
            cmd_type = _TYPE_MAP.get(cmd_name)
            if cmd_type is None:
                logger.warning("Comando desconhecido em config: '%s' — ignorado.", cmd_name)
                continue
            for phrase in (phrases or []):
                normalized = _normalize(phrase)
                self._phrase_map[normalized] = cmd_type
                logger.debug("Comando '%s' mapeado para %s", normalized, cmd_type)

        logger.info(
            "CommandInterpreter carregado com %d frases de controle.", len(self._phrase_map)
        )

    def interpret(self, text: str) -> Union[ControlCommand, str]:
        """
        Classifica o texto transcrito.

        Retorna:
          - ControlCommand se for um comando de controle reconhecido.
          - str (texto original) se for ditado literal.
        """
        if not text or not text.strip():
            logger.debug("Texto vazio recebido pelo interpreter.")
            return ""

        normalized = _normalize(text)
        logger.debug("Interpret: %r → normalizado: %r", text, normalized)

        # Verifica match exato primeiro (mais específico)
        if normalized in self._phrase_map:
            cmd_type = self._phrase_map[normalized]
            logger.info("Comando de controle detectado: %s (%r)", cmd_type.name, text)
            return ControlCommand(type=cmd_type, raw_text=text)

        # Verifica se começa com uma frase de controle (ex: "cancela tudo isso")
        for phrase, cmd_type in sorted(self._phrase_map.items(), key=lambda x: -len(x[0])):
            if normalized.startswith(phrase + " ") or normalized == phrase:
                logger.info(
                    "Comando de controle por prefixo: %s (%r → %r)", cmd_type.name, text, phrase
                )
                return ControlCommand(type=cmd_type, raw_text=text)

        # É ditado literal
        self._last_dictation = text
        logger.debug("Ditado: %r", text)
        return text

    def execute_control(self, command: ControlCommand, ctx: dict) -> Optional[str]:
        """Executa um comando de controle e retorna mensagem de status."""
        handler = HANDLERS.get(command.type)
        if handler is None:
            logger.error("Sem handler para comando: %s", command.type)
            return None
        ctx["last_dictation"] = self._last_dictation
        return handler(ctx)

    @property
    def last_dictation(self) -> Optional[str]:
        return self._last_dictation
