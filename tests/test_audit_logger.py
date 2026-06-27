"""
Testes para o AuditLogger.

Cobre:
- Escrita de diferentes tipos de eventos
- Formato JSON por linha (JSONL)
- Campos obrigatórios presentes
- Ação externa com confirmed=False não é silenciada
- Arquivo desabilitado não cria arquivo
"""

import json
import os
import pytest

from audit import AuditLogger


@pytest.fixture
def audit(cfg, tmp_path):
    cfg.set(str(tmp_path / "audit.jsonl"), "audit", "file")
    cfg.set(True, "audit", "enabled")
    return AuditLogger(cfg)


@pytest.fixture
def audit_file(cfg, tmp_path):
    return str(tmp_path / "audit.jsonl")


def read_entries(file_path: str) -> list[dict]:
    if not os.path.exists(file_path):
        return []
    with open(file_path) as f:
        return [json.loads(line) for line in f if line.strip()]


class TestVoiceInputLog:
    def test_log_voice_input(self, audit, audit_file):
        audit.log_voice_input("print hello", duration_ms=1500, language="pt")
        entries = read_entries(audit_file)
        assert len(entries) == 1
        assert entries[0]["event_type"] == "voice_input"
        assert entries[0]["content"] == "print hello"
        assert entries[0]["metadata"]["language"] == "pt"

    def test_timestamp_presente(self, audit, audit_file):
        audit.log_voice_input("teste", duration_ms=500)
        entries = read_entries(audit_file)
        assert "timestamp" in entries[0]
        assert "T" in entries[0]["timestamp"]

    def test_session_id_consistente(self, audit, audit_file):
        audit.log_voice_input("um", duration_ms=100)
        audit.log_voice_input("dois", duration_ms=100)
        entries = read_entries(audit_file)
        assert entries[0]["session_id"] == entries[1]["session_id"]


class TestClaudeResponseLog:
    def test_log_claude_response(self, audit, audit_file):
        audit.log_claude_response("Aqui está o código.", inference_ms=2000)
        entries = read_entries(audit_file)
        assert entries[0]["event_type"] == "claude_response"
        assert entries[0]["metadata"]["char_count"] == len("Aqui está o código.")

    def test_was_truncated_registrado(self, audit, audit_file):
        audit.log_claude_response("texto", inference_ms=100, was_truncated=True)
        entries = read_entries(audit_file)
        assert entries[0]["metadata"]["was_truncated"] is True


class TestExternalActionLog:
    def test_acao_nao_confirmada_registrada(self, audit, audit_file):
        audit.log_external_action(
            action_type="whatsapp_send",
            description="Enviar 'oi' para João",
            confirmed=False,
            destination="whatsapp:+5511999999999",
        )
        entries = read_entries(audit_file)
        assert entries[0]["confirmed"] is False
        assert entries[0]["event_type"] == "external_action"
        assert entries[0]["metadata"]["REQUIRES_CONFIRMATION"] is True

    def test_acao_confirmada_registrada(self, audit, audit_file):
        audit.log_external_action(
            action_type="browser_submit",
            description="Enviar formulário",
            confirmed=True,
            destination="https://example.com/form",
        )
        entries = read_entries(audit_file)
        assert entries[0]["confirmed"] is True


class TestAuditDisabled:
    def test_desabilitado_nao_cria_arquivo(self, cfg, tmp_path):
        audit_file = str(tmp_path / "audit.jsonl")
        cfg.set(audit_file, "audit", "file")
        cfg.set(False, "audit", "enabled")
        audit = AuditLogger(cfg)
        audit.log_voice_input("teste", duration_ms=100)
        assert not os.path.exists(audit_file)


class TestControlCommandLog:
    def test_log_control_command(self, audit, audit_file):
        audit.log_control_command("CANCELA", "cancela isso")
        entries = read_entries(audit_file)
        assert entries[0]["event_type"] == "control_command"
        assert entries[0]["metadata"]["command"] == "CANCELA"
