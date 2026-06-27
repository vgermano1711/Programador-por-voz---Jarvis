"""Fixtures compartilhadas entre todos os testes."""

import json
import os
import tempfile

import numpy as np
import pytest

from config import load_config
from config.defaults import DEFAULTS


@pytest.fixture
def tmp_config_path(tmp_path):
    """Cria um config.yaml temporário com os defaults."""
    import yaml
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(DEFAULTS), encoding="utf-8")
    return str(config_file)


@pytest.fixture
def cfg(tmp_config_path):
    """Config carregado dos defaults."""
    return load_config(tmp_config_path)


@pytest.fixture
def silent_audio():
    """Array de áudio silencioso (1 segundo a 16kHz)."""
    return np.zeros(16000, dtype=np.float32)


@pytest.fixture
def speech_audio():
    """Array de áudio com energia simulando fala (senoide)."""
    t = np.linspace(0, 1.0, 16000)
    return (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


@pytest.fixture
def tmp_history_file(tmp_path):
    """Arquivo de histórico temporário."""
    return str(tmp_path / "history.json")
