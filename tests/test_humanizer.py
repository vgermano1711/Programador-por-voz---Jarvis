"""
Testes para o Humanizer de respostas.

Cobre:
- Remoção de blocos de código com aviso verbal
- Remoção de Markdown inline
- Normalização de listas
- Truncamento com aviso
- Abreviações
- Texto vazio
- split_into_sentences
"""

import pytest
from response_humanizer import Humanizer


@pytest.fixture
def humanizer(cfg):
    cfg.set(800, "tts", "humanizer_max_chars")
    cfg.set(True, "tts", "humanizer_announce_code")
    return Humanizer(cfg)


class TestCodeRemoval:
    def test_bloco_codigo_removido(self, humanizer):
        text = "Aqui está:\n```python\ndef foo():\n    return 42\n```\nEspero que ajude."
        result = humanizer.humanize(text)
        assert "def foo" not in result
        assert "return 42" not in result

    def test_aviso_codigo_adicionado(self, humanizer):
        text = "Veja:\n```python\nx = 1\n```"
        result = humanizer.humanize(text)
        assert "terminal" in result.lower() or "código" in result.lower()

    def test_codigo_inline_curto_mantido(self, humanizer):
        text = "Use a função `print` para exibir valores."
        result = humanizer.humanize(text)
        assert "print" in result

    def test_codigo_inline_longo_removido(self, humanizer):
        text = "Execute `subprocess.run(['git', 'status'], capture_output=True)`."
        result = humanizer.humanize(text)
        assert "subprocess.run" not in result

    def test_sem_codigo_sem_aviso(self, humanizer):
        text = "Use listas para organizar dados."
        result = humanizer.humanize(text)
        assert "terminal" not in result


class TestMarkdownRemoval:
    def test_remove_bold(self, humanizer):
        text = "Isso é **muito importante** para o sistema."
        result = humanizer.humanize(text)
        assert "**" not in result
        assert "muito importante" in result

    def test_remove_italic(self, humanizer):
        text = "Use *este método* com cuidado."
        result = humanizer.humanize(text)
        assert "*este método*" not in result
        assert "este método" in result

    def test_remove_cabecalhos(self, humanizer):
        text = "## Solução\nAqui está a solução."
        result = humanizer.humanize(text)
        assert "##" not in result
        assert "Solução" in result

    def test_remove_links(self, humanizer):
        text = "Veja a [documentação](https://example.com) oficial."
        result = humanizer.humanize(text)
        assert "https://example.com" not in result
        assert "documentação" in result


class TestListNormalization:
    def test_lista_convertida(self, humanizer):
        text = "Opções:\n- Primeira opção\n- Segunda opção"
        result = humanizer.humanize(text)
        assert "-" not in result or "Primeira opção" in result

    def test_lista_numerada(self, humanizer):
        text = "Passos:\n1. Instale\n2. Configure\n3. Execute"
        result = humanizer.humanize(text)
        # Os números de lista devem ser removidos
        assert "1." not in result


class TestTruncation:
    def test_trunca_texto_longo(self, cfg):
        cfg.set(50, "tts", "humanizer_max_chars")
        h = Humanizer(cfg)
        long_text = "Esta é uma frase muito longa. " * 10
        result = h.humanize(long_text)
        assert len(result) < len(long_text)
        assert "terminal" in result.lower()

    def test_texto_curto_nao_truncado(self, humanizer):
        text = "Isso funciona perfeitamente."
        result = humanizer.humanize(text)
        assert "terminal" not in result


class TestEdgeCases:
    def test_texto_vazio(self, humanizer):
        assert humanizer.humanize("") == ""

    def test_apenas_codigo(self, humanizer):
        text = "```python\nx = 1\n```"
        result = humanizer.humanize(text)
        # Deve retornar o aviso de código
        assert result  # não deve ser vazio

    def test_split_sentences(self, humanizer):
        text = "Primeira frase. Segunda frase! Terceira frase?"
        sentences = humanizer.split_into_sentences(text)
        assert len(sentences) == 3
        assert sentences[0] == "Primeira frase."
