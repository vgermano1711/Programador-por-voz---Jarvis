# J.A.R.V.I.S — Assistente Pessoal de Voz de Victor Germano

> Eu construí o Jarvis. De verdade.

Não o personagem de ficção — mas o mais próximo que a tecnologia atual permite.

Por anos assisti ao Tony Stark falar com uma IA que o entendia, aconselhava, executava tarefas e alertava sobre riscos em tempo real. Decidi parar de assistir e construir.

---

## O que é

Um assistente pessoal de IA com voz bidirecional, rodando localmente no Windows, integrado ao meu ambiente de desenvolvimento. Ele me ouve, raciocina, aconselha e responde em voz — em menos de 1 segundo.

```
[Você segura Ctrl+R e fala]
Victor: "Jarvis, essa função está grande demais."

[~1s depois, Jarvis responde em voz]
Jarvis: "Victor, ela tem três responsabilidades distintas.
         Eu quebraria em duas. Quer que eu faça agora?"
```

Ele não só executa — ele opina, sugere alternativas, avisa quando algo pode dar errado e diz quando não sabe.

---

## O que ele faz hoje

| Funcionalidade | Detalhe |
|---|---|
| **Voz bidirecional** | Responde em ~1s, frase a frase, enquanto ainda está pensando |
| **Roteamento de modelos** | Escolhe automaticamente entre Haiku, Sonnet e Opus pela complexidade |
| **Memória persistente** | Lembra conversas e decisões entre sessões (SQLite) |
| **Detecção de emoção** | Detecta estresse, animação ou cansaço no tom de voz e ajusta a resposta |
| **Contexto do VS Code** | Sabe qual arquivo você está editando e usa como contexto |
| **Spotify** | "toca The Weeknd", "próxima", "volume 70" |
| **Google Calendar/Gmail** | "o que tenho hoje?", "quantos emails não lidos?" |
| **GitHub** | "quais são as PRs abertas?", "últimos commits", "cria issue" |
| **Monitor proativo** | Detecta erros no terminal e avisa em voz automaticamente |
| **Dashboard web** | Interface em localhost:7432 com histórico de conversas |
| **HUD estilo Iron Man** | Overlay visual que pulsa enquanto ouve |

---

## Pipeline

```
Microfone (push-to-talk: Ctrl+R)
   ↓
faster-whisper — transcrição local em ~0.3s
   ↓
Detecção de emoção no tom de voz
   ↓
ModelRouter — Haiku / Sonnet / Opus (automático)
   ↓
Claude API (Anthropic) — resposta em ~0.8s
   ↓
Humanizer — remove markdown, bullets, código
   ↓
Edge TTS (pt-BR-AntonioNeural) — streaming por frase
   ↓
Alto-falante

Latência total: ~1s da fala até o Jarvis começar a responder.
```

---

## Stack

`faster-whisper` · `Claude API (Anthropic)` · `Edge TTS` · `Spotify API` · `Google Calendar/Gmail API` · `GitHub API` · `SQLite` · `Flask` · `pynput` · `tkinter` · Python puro

96 testes unitários. Setup automático em um comando.

---

## Instalação

```powershell
git clone https://github.com/vgermano1711/Programador-por-voz---Jarvis
cd Programador-por-voz---Jarvis
pip install -r requirements.txt
set ANTHROPIC_API_KEY=sk-ant-...
py main.py
```

## Configurar integrações

```powershell
py setup_integrations.py
```

Guia interativo que configura Spotify, GitHub e Google automaticamente.

---

## Arquitetura

```
jarvis/
├── main.py                    # Orquestrador principal
├── config.yaml                # Configuração completa
├── CLAUDE.md                  # Personalidade do Jarvis
├── setup_integrations.py      # Wizard de configuração
├── audio_capture/             # Captura de áudio e push-to-talk
├── transcription/             # Whisper (faster-whisper)
├── response_capture/          # Cliente API Anthropic
├── model_router/              # Roteamento Haiku/Sonnet/Opus
├── memory/                    # Memória persistente (SQLite)
├── emotion/                   # Detecção de emoção no tom de voz
├── integrations/              # Spotify, GitHub, Google, VS Code
├── proactive/                 # Monitor de erros no terminal
├── dashboard/                 # Dashboard web (Flask)
├── tts/                       # Síntese de voz (edge-tts)
├── tray/                      # Bandeja do sistema + overlay HUD
└── tests/                     # 96 testes unitários
```

---

## Licença

MIT — use, modifique e distribua à vontade.

---

Construído por **Victor Germano** com assistência do Claude Code (Anthropic).
