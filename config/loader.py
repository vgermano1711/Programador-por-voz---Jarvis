"""
Carrega, valida e persiste a configuração do sistema.

Estratégia de merge: config.yaml sobrescreve valores de DEFAULTS, mas campos
ausentes no yaml ficam com o valor padrão — assim novos campos adicionados no
código não quebram configs antigas dos usuários.
"""

import copy
import os
from typing import Any, Optional

import yaml

from .defaults import DEFAULTS
from logging_setup import get_logger

logger = get_logger(__name__)

_DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.yaml")


class Config:
    """Wrapper sobre o dicionário de configuração com acesso por atributo aninhado."""

    def __init__(self, data: dict) -> None:
        self._data = data

    def get(self, *keys: str, default: Any = None) -> Any:
        """Acesso seguro a chaves aninhadas: cfg.get('audio', 'sample_rate')."""
        node = self._data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def set(self, value: Any, *keys: str) -> None:
        """Define valor em chave aninhada: cfg.set(16000, 'audio', 'sample_rate')."""
        node = self._data
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = value

    def as_dict(self) -> dict:
        return copy.deepcopy(self._data)

    def __repr__(self) -> str:
        return f"Config({list(self._data.keys())})"


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge recursivo: override sobrescreve base sem apagar chaves ausentes."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config(path: Optional[str] = None) -> Config:
    """
    Carrega config do arquivo yaml e faz merge com os defaults.
    Se o arquivo não existir, usa apenas os defaults e registra aviso.
    """
    config_path = path or _DEFAULT_CONFIG_PATH

    data = copy.deepcopy(DEFAULTS)

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
            data = _deep_merge(data, user_config)
            logger.info("Configuração carregada de: %s", config_path)
        except yaml.YAMLError as exc:
            logger.error("Erro ao parsear config.yaml: %s — usando defaults", exc)
        except OSError as exc:
            logger.error("Erro ao ler config.yaml: %s — usando defaults", exc)
    else:
        logger.warning(
            "Arquivo de configuração não encontrado em '%s'. Usando defaults.", config_path
        )

    return Config(data)


def save_config(cfg: Config, path: Optional[str] = None) -> None:
    """Persiste a configuração atual no arquivo yaml."""
    config_path = path or _DEFAULT_CONFIG_PATH
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(cfg.as_dict(), f, allow_unicode=True, sort_keys=False)
        logger.info("Configuração salva em: %s", config_path)
    except OSError as exc:
        logger.error("Falha ao salvar configuração: %s", exc)
