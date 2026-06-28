# 🎙️ Jarvis — Assistente de Voz com IA

Assistente de voz pessoal integrado à API da Anthropic (Claude). Fale, e o Jarvis responde com voz em tempo real — como no Homem de Ferro, mas rodando no seu PC.

## Demo

```
[Você pressiona Ctrl direito e fala]
Victor: "Qual a capital da Austrália?"

[~1.5 segundos depois, Jarvis responde em voz]
Jarvis: "Canberra, Victor. Não Sydney — um erro comum."
```

## Como funciona

```
Microfone
   │  (push-to-talk: Ctrl direito)
   ▼
Whisper (faster-whisper, tiny, local)
   │  transcrição em ~0.3s
   ▼
API Anthropic (Claude Haiku)
   │  resposta em ~0.8s
   ▼
Edge TTS (pt-BR-AntonioNeural, gratuito)
   │  síntese em ~0.3s
   ▼
Alto-falante
```

**Latência total: ~1.5s** da fala até o Jarvis começar a responder.

## Stack

| Componente | Tecnologia |
|---|---|
| Reconhecimento de voz | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (Whisper tiny, local, CPU) |
| IA / Resposta | [Anthropic Claude Haiku](https://anthropic.com) via API |
| Síntese de voz | [edge-tts](https://github.com/rany2/edge-tts) (Microsoft Edge, gratuito) |
| Push-to-talk | [pynput](https://pynput.readthedocs.io) (Ctrl direito) |
| Áudio | sounddevice + miniaudio |
| Interface | pystray (bandeja do sistema) |

## Requisitos

- Python 3.10+
- Windows 10/11 (testado) ou Linux
- Microfone
- Chave de API da Anthropic ([console.anthropic.com](https://console.anthropic.com))
- Conexão com internet (para API e TTS)

## Instalação

```bash
git clone https://github.com/seu-usuario/jarvis-voice-assistant
cd jarvis-voice-assistant

pip install -r requirements.txt

# Configure sua chave de API
set ANTHROPIC_API_KEY=sk-ant-...   # Windows
export ANTHROPIC_API_KEY=sk-ant-... # Linux/Mac
```

## Uso

```bash
python main.py
```

Aguarde `Sistema pronto! Segure CTRL_R e fale.`

Segure **Ctrl direito** → fale → solte → Jarvis responde.

## Configuração

Edite `config.yaml` para personalizar:

```yaml
activation:
  push_to_talk_key: "ctrl_r"   # Tecla de ativação

tts:
  edge_voice: pt-BR-AntonioNeural  # Voz
  edge_rate: "+15%"                # Velocidade
  edge_pitch: "+8Hz"               # Tom

transcription:
  model: tiny    # tiny/base/small/medium/large-v3
  language: pt   # Idioma
```

## Personalidade

O Jarvis tem uma personalidade configurável via `CLAUDE.md` — tom formal, chama você pelo nome, respostas curtas otimizadas para voz.

## Funcionalidades

- Push-to-talk com tecla configurável
- Histórico de conversa entre chamadas (contexto mantido)
- Streaming de TTS: começa a falar antes de terminar de pensar
- Ícone na bandeja do sistema com status visual
- Overlay de status na tela
- Log de auditoria de todas as interações
- Comando de voz "para de falar" / "espera" para silenciar

## Arquitetura

```
programador_por_voz/
├── main.py                    # Orquestrador principal
├── config.yaml                # Configuração completa
├── CLAUDE.md                  # Personalidade do Jarvis
├── audio_capture/             # Captura de áudio e push-to-talk
├── transcription/             # Whisper (faster-whisper)
├── response_capture/          # Cliente API Anthropic
├── tts/                       # Síntese de voz (edge-tts)
│   ├── edge_engine.py
│   ├── streaming_pipeline.py  # TTS frase a frase
│   └── player.py
├── tray/                      # Bandeja do sistema + overlay
└── tests/                     # Testes unitários
```

## Licença

MIT — use, modifique e distribua à vontade.

---

Construído por **Victor Germano** com assistência do Claude Code (Anthropic).
