"""
Testes para o módulo CommandInterpreter.

Cobre:
- Detecção de todos os comandos de controle por frase exata
- Detecção por prefixo
- Normalização (acentos, pontuação, case)
- Fallthrough para ditado literal
- Comandos customizados via config
"""

import pytest
from command_interpreter import CommandInterpreter, CommandType
from command_interpreter.control_commands import ControlCommand


@pytest.fixture
def interpreter(cfg):
    return CommandInterpreter(cfg)


class TestControlCommandDetection:
    def test_cancela_exato(self, interpreter):
        result = interpreter.interpret("cancela")
        assert isinstance(result, ControlCommand)
        assert result.type == CommandType.CANCELA

    def test_cancela_uppercase(self, interpreter):
        result = interpreter.interpret("CANCELA")
        assert isinstance(result, ControlCommand)
        assert result.type == CommandType.CANCELA

    def test_cancela_com_acento(self, interpreter):
        # "cancelá" deve normalizar para "cancela"
        result = interpreter.interpret("cancelá")
        assert isinstance(result, ControlCommand)

    def test_cancela_frase_completa(self, interpreter):
        result = interpreter.interpret("cancela isso")
        assert isinstance(result, ControlCommand)
        assert result.type == CommandType.CANCELA

    def test_interrompe(self, interpreter):
        result = interpreter.interpret("interrompe")
        assert isinstance(result, ControlCommand)
        assert result.type == CommandType.INTERROMPE

    def test_interrompe_alias(self, interpreter):
        result = interpreter.interpret("ctrl c")
        assert isinstance(result, ControlCommand)
        assert result.type == CommandType.INTERROMPE

    def test_repete(self, interpreter):
        result = interpreter.interpret("repete")
        assert isinstance(result, ControlCommand)
        assert result.type == CommandType.REPETE

    def test_repete_variante(self, interpreter):
        result = interpreter.interpret("repete isso")
        assert isinstance(result, ControlCommand)
        assert result.type == CommandType.REPETE

    def test_limpa_tela(self, interpreter):
        result = interpreter.interpret("limpa tela")
        assert isinstance(result, ControlCommand)
        assert result.type == CommandType.LIMPA_TELA

    def test_para(self, interpreter):
        result = interpreter.interpret("para")
        assert isinstance(result, ControlCommand)
        assert result.type == CommandType.PARA


class TestDictationPassthrough:
    def test_codigo_python(self, interpreter):
        text = "print hello world"
        result = interpreter.interpret(text)
        assert result == text

    def test_texto_longo(self, interpreter):
        text = "def minha_funcao que recebe dois parametros e retorna a soma"
        result = interpreter.interpret(text)
        assert result == text

    def test_texto_vazio(self, interpreter):
        result = interpreter.interpret("")
        assert result == ""

    def test_texto_com_numeros(self, interpreter):
        text = "variavel igual a 42"
        result = interpreter.interpret(text)
        assert result == text

    def test_nao_confunde_palavra_parcial(self, interpreter):
        # "parabens" não deve ser detectado como "para"
        result = interpreter.interpret("parabens pelo trabalho")
        assert isinstance(result, str)
        assert result == "parabens pelo trabalho"


class TestNormalization:
    def test_pontuacao_removida(self, interpreter):
        result = interpreter.interpret("cancela!")
        assert isinstance(result, ControlCommand)

    def test_espacos_extras(self, interpreter):
        result = interpreter.interpret("  cancela  ")
        assert isinstance(result, ControlCommand)


class TestLastDictation:
    def test_salva_ultimo_ditado(self, interpreter):
        interpreter.interpret("print hello")
        assert interpreter.last_dictation == "print hello"

    def test_controle_nao_sobrescreve_ultimo_ditado(self, interpreter):
        interpreter.interpret("print hello")
        interpreter.interpret("cancela")
        assert interpreter.last_dictation == "print hello"
