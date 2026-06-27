"""
Testes para ClaudeCapture (captura de resposta via subprocess).

Todos os testes mockam subprocess.run para não depender do Claude Code instalado.
Cobre:
- Resposta bem-sucedida
- Timeout
- Binário não encontrado
- Histórico de contexto
- Erro de return code
"""

import subprocess
import pytest
from unittest.mock import patch, MagicMock

from response_capture import ClaudeCapture


@pytest.fixture
def capture(cfg):
    cfg.set("claude", "claude_capture", "claude_bin")
    cfg.set(10, "claude_capture", "timeout_seconds")
    cfg.set(5, "claude_capture", "max_history_turns")
    return ClaudeCapture(cfg)


def make_completed_process(stdout="resposta do claude", returncode=0, stderr=""):
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.stdout = stdout
    proc.returncode = returncode
    proc.stderr = stderr
    return proc


class TestSend:
    def test_resposta_simples(self, capture):
        with patch("subprocess.run", return_value=make_completed_process("Olá! Como posso ajudar?")):
            result = capture.send("oi")
        assert result == "Olá! Como posso ajudar?"

    def test_retorna_none_em_erro(self, capture):
        with patch("subprocess.run", return_value=make_completed_process("", returncode=1, stderr="error")):
            result = capture.send("oi")
        assert result is None

    def test_retorna_none_em_timeout(self, capture):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 10)):
            result = capture.send("oi")
        assert result is None

    def test_retorna_none_se_binario_nao_encontrado(self, capture):
        with patch("subprocess.run", side_effect=FileNotFoundError("claude not found")):
            result = capture.send("oi")
        assert result is None

    def test_strip_whitespace(self, capture):
        with patch("subprocess.run", return_value=make_completed_process("  resposta  \n")):
            result = capture.send("oi")
        assert result == "resposta"

    def test_resposta_vazia_retorna_none(self, capture):
        with patch("subprocess.run", return_value=make_completed_process("   ")):
            result = capture.send("oi")
        assert result is None


class TestHistory:
    def test_historico_acumula(self, capture):
        with patch("subprocess.run", return_value=make_completed_process("resposta 1")):
            capture.send("pergunta 1")
        assert len(capture._history) == 1

    def test_historico_incluido_no_proximo_prompt(self, capture):
        with patch("subprocess.run", return_value=make_completed_process("resposta 1")) as mock_run:
            capture.send("pergunta 1")

        with patch("subprocess.run", return_value=make_completed_process("resposta 2")) as mock_run:
            capture.send("pergunta 2")
            call_args = mock_run.call_args[0][0]  # args do subprocess.run
            # O prompt deve conter o histórico
            prompt_arg = call_args[2]  # terceiro arg é o prompt
            assert "pergunta 1" in prompt_arg
            assert "resposta 1" in prompt_arg

    def test_limpar_historico(self, capture):
        with patch("subprocess.run", return_value=make_completed_process("resp")):
            capture.send("msg")
        assert len(capture._history) == 1
        capture.clear_history()
        assert len(capture._history) == 0


class TestSendAsync:
    def test_callback_chamado(self, capture):
        received = []

        def callback(resp):
            received.append(resp)

        with patch("subprocess.run", return_value=make_completed_process("async resposta")):
            thread = capture.send_async("oi", on_response=callback)
            thread.join(timeout=3)

        assert received == ["async resposta"]

    def test_callback_nao_chamado_em_erro(self, capture):
        received = []

        def callback(resp):
            received.append(resp)

        with patch("subprocess.run", return_value=make_completed_process("", returncode=1)):
            thread = capture.send_async("oi", on_response=callback)
            thread.join(timeout=3)

        assert received == []
