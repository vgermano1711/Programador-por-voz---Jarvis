"""
Testes para o HistoryManager.

Cobre:
- Adição de entradas (ditado e controle)
- Rotação ao atingir max_entries
- Recuperação do último ditado
- Formato correto do JSON
- Comportamento com histórico desabilitado
"""

import json
import os
import pytest

from history import HistoryManager


@pytest.fixture
def history(cfg, tmp_history_file):
    cfg.set(tmp_history_file, "history", "file")
    cfg.set(True, "history", "enabled")
    return HistoryManager(cfg)


@pytest.fixture
def history_disabled(cfg, tmp_history_file):
    cfg.set(tmp_history_file, "history", "file")
    cfg.set(False, "history", "enabled")
    return HistoryManager(cfg)


class TestHistoryAdd:
    def test_adiciona_entrada_ditado(self, history, tmp_history_file):
        history.add("print hello", entry_type="dictation")
        with open(tmp_history_file) as f:
            entries = json.load(f)
        assert len(entries) == 1
        assert entries[0]["text"] == "print hello"
        assert entries[0]["type"] == "dictation"

    def test_adiciona_entrada_controle(self, history, tmp_history_file):
        history.add("cancela", entry_type="control", command="CANCELA")
        with open(tmp_history_file) as f:
            entries = json.load(f)
        assert entries[0]["command"] == "CANCELA"
        assert entries[0]["type"] == "control"

    def test_timestamp_presente(self, history, tmp_history_file):
        history.add("teste")
        with open(tmp_history_file) as f:
            entries = json.load(f)
        assert "timestamp" in entries[0]
        assert "T" in entries[0]["timestamp"]  # formato ISO 8601

    def test_multiplas_entradas(self, history, tmp_history_file):
        history.add("primeiro")
        history.add("segundo")
        history.add("terceiro")
        with open(tmp_history_file) as f:
            entries = json.load(f)
        assert len(entries) == 3

    def test_com_metadados(self, history, tmp_history_file):
        history.add("teste", language="pt", inference_ms=1500, success=True)
        with open(tmp_history_file) as f:
            entries = json.load(f)
        assert entries[0]["language"] == "pt"
        assert entries[0]["inference_ms"] == 1500


class TestHistoryRotation:
    def test_rotacao_ao_atingir_max(self, cfg, tmp_history_file):
        cfg.set(tmp_history_file, "history", "file")
        cfg.set(3, "history", "max_entries")
        h = HistoryManager(cfg)

        for i in range(5):
            h.add(f"entrada {i}")

        with open(tmp_history_file) as f:
            entries = json.load(f)

        assert len(entries) == 3
        # Mantém as mais recentes
        assert entries[-1]["text"] == "entrada 4"
        assert entries[0]["text"] == "entrada 2"


class TestGetLastDictation:
    def test_retorna_ultimo_ditado(self, history):
        history.add("primeiro", entry_type="dictation", success=True)
        history.add("cancela", entry_type="control", command="CANCELA")
        history.add("segundo", entry_type="dictation", success=True)
        assert history.get_last_dictation() == "segundo"

    def test_ignora_falhas(self, history):
        history.add("falhou", entry_type="dictation", success=False)
        history.add("sucesso", entry_type="dictation", success=True)
        assert history.get_last_dictation() == "sucesso"

    def test_retorna_none_sem_ditado(self, history):
        history.add("cancela", entry_type="control")
        assert history.get_last_dictation() is None


class TestHistoryDisabled:
    def test_nao_cria_arquivo(self, history_disabled, tmp_history_file):
        history_disabled.add("teste")
        assert not os.path.exists(tmp_history_file)

    def test_get_last_retorna_lista_vazia(self, history_disabled):
        assert history_disabled.get_last() == []
