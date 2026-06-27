"""
Testes para carregamento e persistência de configuração.

Cobre:
- Carregamento de arquivo válido
- Merge com defaults (campos ausentes preenchidos)
- Arquivo inexistente → usa defaults
- YAML inválido → usa defaults sem crash
- Salvar e recarregar preserva valores
- Acesso seguro a chaves aninhadas
"""

import os
import pytest
import yaml

from config import load_config, save_config, Config
from config.defaults import DEFAULTS


class TestLoadConfig:
    def test_carrega_defaults_sem_arquivo(self, tmp_path):
        cfg = load_config(str(tmp_path / "nao_existe.yaml"))
        assert cfg.get("transcription", "model") == DEFAULTS["transcription"]["model"]

    def test_carrega_arquivo_valido(self, tmp_config_path):
        cfg = load_config(tmp_config_path)
        assert cfg.get("activation", "mode") == "push_to_talk"

    def test_sobrescreve_valor(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({"transcription": {"model": "medium"}}), encoding="utf-8"
        )
        cfg = load_config(str(config_file))
        assert cfg.get("transcription", "model") == "medium"

    def test_merge_preserva_outros_campos(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({"transcription": {"model": "large-v3"}}), encoding="utf-8"
        )
        cfg = load_config(str(config_file))
        # Campo não sobrescrito deve vir do default
        assert cfg.get("transcription", "beam_size") == DEFAULTS["transcription"]["beam_size"]

    def test_yaml_invalido_usa_defaults(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(":::invalid yaml:::", encoding="utf-8")
        cfg = load_config(str(config_file))
        # Deve usar defaults sem crash
        assert cfg.get("activation", "mode") == "push_to_talk"

    def test_chave_inexistente_retorna_default(self, cfg):
        result = cfg.get("nao_existe", "chave", default="fallback")
        assert result == "fallback"

    def test_chave_aninhada_inexistente(self, cfg):
        result = cfg.get("activation", "chave_falsa", default=42)
        assert result == 42


class TestSaveConfig:
    def test_salvar_e_recarregar(self, tmp_path, cfg):
        save_path = str(tmp_path / "saved.yaml")
        cfg.set("large-v3", "transcription", "model")
        save_config(cfg, save_path)

        reloaded = load_config(save_path)
        assert reloaded.get("transcription", "model") == "large-v3"

    def test_salvar_unicode(self, tmp_path, cfg):
        save_path = str(tmp_path / "unicode.yaml")
        cfg.set("Código Python, programação.", "transcription", "initial_prompt")
        save_config(cfg, save_path)

        reloaded = load_config(save_path)
        assert "programação" in reloaded.get("transcription", "initial_prompt")


class TestConfigSetGet:
    def test_set_get_simples(self, cfg):
        cfg.set("cuda", "transcription", "device")
        assert cfg.get("transcription", "device") == "cuda"

    def test_as_dict_retorna_copia(self, cfg):
        d = cfg.as_dict()
        d["novo_campo"] = "valor"
        assert cfg.get("novo_campo") is None
