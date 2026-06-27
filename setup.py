#!/usr/bin/env python3
"""
Setup automático do Programador por Voz.

Executa em sequência, detectando o ambiente e instalando apenas o necessário:
  1. Dependências Python (pip)
  2. Dependências de sistema (apt/brew/choco)
  3. Modelo Whisper (download automático pelo faster-whisper)
  4. Modelo TTS Coqui (download automático)
  5. Servidores MCP via npm (filesystem, playwright)
  6. Configuração do Claude Code (mcp.json)
  7. Teste de fumaça de cada componente

Uso:
    python setup.py                  # setup completo
    python setup.py --skip-tts       # pula download do modelo TTS (~120MB)
    python setup.py --skip-mcp       # pula instalação npm dos servidores MCP
    python setup.py --tts elevenlabs # configura ElevenLabs em vez de Coqui
    python setup.py --check          # só verifica o que está instalado
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# ── Cores para terminal ─────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✓{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET} {msg}")
def err(msg):  print(f"  {RED}✗{RESET} {msg}")
def info(msg): print(f"  {BLUE}→{RESET} {msg}")
def step(msg): print(f"\n{BOLD}{msg}{RESET}")


# ── Detecção de sistema ─────────────────────────────────────────────────────────

SYSTEM = platform.system()  # "Linux" | "Windows" | "Darwin"
IS_LINUX   = SYSTEM == "Linux"
IS_WINDOWS = SYSTEM == "Windows"
IS_MAC     = SYSTEM == "Darwin"

PROJECT_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = PROJECT_DIR / "config.yaml"
MCP_CONFIG_PATH = Path.home() / ".claude" / "mcp.json"


def run(cmd: list[str], check: bool = True, capture: bool = True, **kwargs) -> subprocess.CompletedProcess:
    """Roda comando e retorna resultado. Não lança exceção se check=False."""
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
        **kwargs,
    )


def run_pip(*packages: str, upgrade: bool = False, quiet: bool = False) -> bool:
    """Instala pacotes pip com saída limpa."""
    cmd = [sys.executable, "-m", "pip", "install"]
    if upgrade:
        cmd.append("--upgrade")
    if quiet:
        cmd.append("-q")
    cmd.extend(packages)
    try:
        result = subprocess.run(cmd, capture_output=quiet, text=True)
        return result.returncode == 0
    except Exception:
        return False


def can_import(module: str) -> bool:
    """Verifica se módulo Python pode ser importado."""
    try:
        __import__(module)
        return True
    except ImportError:
        return False


def cmd_exists(name: str) -> bool:
    return shutil.which(name) is not None


# ── Etapas de instalação ────────────────────────────────────────────────────────

def step_python_deps(args) -> bool:
    step("1/7 — Dependências Python")

    # Core sempre instalado
    core = [
        "sounddevice", "numpy", "PyYAML", "pynput",
        "pyperclip", "pyautogui", "pystray", "Pillow",
        "colorlog", "pytest", "pytest-mock",
    ]

    # faster-whisper
    whisper_pkg = ["faster-whisper"]

    # TTS
    if not args.skip_tts:
        if args.tts == "coqui":
            tts_pkg = ["TTS"]
        else:
            tts_pkg = ["keyring", "keyrings.alt"]
    else:
        tts_pkg = []

    # keyring para credenciais
    cred_pkg = ["keyring", "keyrings.alt"]

    all_packages = core + whisper_pkg + tts_pkg + cred_pkg

    # Pacotes que podem falhar em ambientes headless/sem display — não são bloqueantes
    optional_display = {"pyautogui", "pynput", "pystray"}

    info(f"Instalando {len(all_packages)} pacotes...")
    ok_count = 0
    for pkg in all_packages:
        success = run_pip(pkg, quiet=True)
        if success:
            ok_count += 1
        elif pkg in optional_display:
            warn(f"{pkg} não instalado — pode requerer display (X11/Wayland). Funcionará no desktop.")
        else:
            warn(f"Falha ao instalar {pkg} — continuando")

    ok(f"{ok_count}/{len(all_packages)} pacotes instalados.")
    return True


def step_system_deps() -> bool:
    step("2/7 — Dependências de sistema")

    if IS_LINUX:
        _install_linux_deps()
    elif IS_MAC:
        _install_mac_deps()
    elif IS_WINDOWS:
        _check_windows_deps()

    return True


def _install_linux_deps():
    """Instala dependências de sistema no Linux via apt."""
    needed = []

    if not cmd_exists("xdotool"):
        needed.append("xdotool")

    # PortAudio para sounddevice
    try:
        import sounddevice as sd
        sd.query_devices()  # testa se funciona
    except Exception:
        needed.extend(["libportaudio2", "portaudio19-dev"])

    # libcairo para pystray no Linux
    try:
        import pystray
    except Exception:
        needed.append("libcairo2-dev")

    if not needed:
        ok("Todas as dependências de sistema já instaladas.")
        return

    info(f"Instalando via apt: {', '.join(needed)}")
    try:
        result = subprocess.run(
            ["sudo", "apt-get", "install", "-y", "--no-install-recommends"] + needed,
            capture_output=False,
        )
        if result.returncode == 0:
            ok("Dependências de sistema instaladas.")
        else:
            warn("Algumas dependências podem ter falhado — verifique manualmente.")
    except FileNotFoundError:
        warn("sudo/apt não disponível. Instale manualmente:")
        for pkg in needed:
            print(f"    sudo apt install {pkg}")


def _install_mac_deps():
    if not cmd_exists("brew"):
        warn("Homebrew não encontrado. Instale em: https://brew.sh")
        return
    packages = ["portaudio", "xdotool"]
    for pkg in packages:
        try:
            run(["brew", "install", pkg], capture=True)
            ok(f"brew install {pkg}")
        except Exception:
            warn(f"Falha ao instalar {pkg} via brew.")


def _check_windows_deps():
    # No Windows, sounddevice usa DirectSound (não precisa de PortAudio extra)
    # pyautogui funciona nativamente
    ok("Windows: dependências de sistema gerenciadas automaticamente.")
    if not cmd_exists("xdotool"):
        warn("xdotool não disponível no Windows — detecção de janela ativa limitada.")


def step_download_whisper_model(args) -> bool:
    step("3/7 — Modelo Whisper (faster-whisper)")

    model_name = args.whisper_model
    info(f"Modelo selecionado: {model_name}")
    _print_whisper_tradeoffs()

    try:
        from faster_whisper import WhisperModel
        info(f"Baixando/carregando modelo '{model_name}'... (pode demorar na 1ª execução)")
        t0 = time.time()
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        elapsed = time.time() - t0
        ok(f"Modelo '{model_name}' pronto ({elapsed:.1f}s).")
        del model  # libera memória
        return True
    except ImportError:
        err("faster-whisper não instalado. Rode sem --skip-deps primeiro.")
        return False
    except Exception as exc:
        exc_str = str(exc)
        if "403" in exc_str or "Forbidden" in exc_str or "network" in exc_str.lower():
            warn(
                f"Download do modelo bloqueado pela rede (403 Forbidden).\n"
                f"    O modelo será baixado automaticamente na primeira execução do sistema.\n"
                f"    Origem: https://huggingface.co/Systran/faster-whisper-{model_name}"
            )
            return True   # não é erro fatal — o modelo baixa no primeiro uso
        err(f"Falha ao carregar modelo Whisper: {exc}")
        return False


def _print_whisper_tradeoffs():
    tradeoffs = {
        "tiny":     ("~39MB",   "<1s",  "baixa"),
        "base":     ("~74MB",   "~1s",  "razoável"),
        "small":    ("~244MB",  "~2s",  "boa ← padrão"),
        "medium":   ("~769MB",  "~4s",  "alta"),
        "large-v3": ("~1.5GB",  "~8s",  "máxima"),
    }
    print(f"    {'Modelo':<12} {'Tamanho':<10} {'Latência':<10} {'Precisão pt-BR'}")
    print(f"    {'-'*50}")
    for name, (size, lat, prec) in tradeoffs.items():
        print(f"    {name:<12} {size:<10} {lat:<10} {prec}")
    print()


def step_download_tts_model(args) -> bool:
    step("4/7 — Modelo TTS (síntese de voz)")

    if args.skip_tts:
        warn("Download TTS pulado (--skip-tts). Respostas não serão faladas até configurar.")
        return True

    if args.tts == "elevenlabs":
        info("ElevenLabs selecionado. Configure a API key:")
        print(f"    export ELEVENLABS_API_KEY=sua_key")
        print(f"    # ou:")
        print(f"    python -c \"from audit.credentials import set_credential; set_credential('elevenlabs', 'SUA_KEY')\"")
        ok("ElevenLabs configurado via variável de ambiente.")
        _update_config("tts", "engine", "elevenlabs")
        return True

    # Coqui TTS
    try:
        from TTS.api import TTS
    except ImportError:
        err("Coqui TTS não instalado. Execute: pip install TTS")
        return False

    model_name = "tts_models/pt/cv/vits"
    info(f"Baixando modelo TTS: {model_name} (~120MB, apenas 1ª vez)...")
    try:
        t0 = time.time()
        tts = TTS(model_name=model_name, gpu=False)
        elapsed = time.time() - t0
        ok(f"Modelo TTS '{model_name}' pronto ({elapsed:.1f}s).")

        # Teste rápido de síntese
        info("Testando síntese de voz...")
        samples = tts.tts("Sistema de voz iniciado com sucesso.")
        if samples:
            ok("Teste de síntese concluído.")
        del tts
        return True
    except Exception as exc:
        err(f"Falha ao carregar TTS: {exc}")
        warn("O sistema funcionará sem saída de voz. Adicione '--skip-tts' se quiser ignorar isso.")
        return False


def step_mcp_servers(args) -> bool:
    step("5/7 — Servidores MCP (Model Context Protocol)")

    if args.skip_mcp:
        warn("Instalação MCP pulada (--skip-mcp).")
        return True

    if not cmd_exists("npm"):
        warn("npm não encontrado. Servidores MCP não serão instalados.")
        warn("Instale Node.js em: https://nodejs.org")
        return False

    node_version = run(["node", "--version"], check=False).stdout.strip()
    info(f"Node.js: {node_version}")

    mcp_packages = {
        "filesystem": "@modelcontextprotocol/server-filesystem",
        "browser":    "@playwright/mcp",
    }

    for name, pkg in mcp_packages.items():
        info(f"Instalando MCP {name}: {pkg}")
        try:
            result = run(
                ["npm", "install", "-g", pkg],
                check=False,
                capture=True,
            )
            if result.returncode == 0:
                ok(f"MCP {name} instalado ({pkg}).")
            else:
                warn(f"MCP {name} falhou: {result.stderr[:100]}")
        except Exception as exc:
            warn(f"MCP {name}: {exc}")

    # Instala browsers do Playwright
    info("Instalando browsers Playwright (Chromium)...")
    try:
        result = run(["npx", "playwright", "install", "chromium"], check=False, capture=True)
        if result.returncode == 0:
            ok("Playwright Chromium instalado.")
        else:
            warn("Playwright install falhou — browser MCP pode não funcionar.")
    except Exception:
        warn("npx playwright install falhou.")

    return True


def step_configure_claude_code(args) -> bool:
    step("6/7 — Configuração do Claude Code")

    # Verifica se claude CLI está disponível
    if not cmd_exists("claude"):
        warn("Claude Code CLI não encontrado no PATH.")
        warn("Instale com: npm install -g @anthropic-ai/claude-code")
        warn("Depois configure a API key: claude --api-key SUA_KEY")
        return False

    claude_version = run(["claude", "--version"], check=False).stdout.strip()
    ok(f"Claude Code encontrado: {claude_version or 'versão desconhecida'}")

    # Cria ~/.claude/mcp.json com servidores configurados
    _write_mcp_json(args)

    # Verifica se CLAUDE.md existe no projeto
    claude_md = PROJECT_DIR / "CLAUDE.md"
    if claude_md.exists():
        ok(f"CLAUDE.md encontrado em {claude_md}")
    else:
        warn("CLAUDE.md não encontrado — comportamento conversacional não personalizado.")

    return True


def _write_mcp_json(args):
    """Escreve ~/.claude/mcp.json com os servidores MCP configurados."""
    if args.skip_mcp:
        return

    MCP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Carrega config existente se houver
    existing = {}
    if MCP_CONFIG_PATH.exists():
        try:
            with open(MCP_CONFIG_PATH) as f:
                existing = json.load(f)
        except Exception:
            existing = {}

    # Adiciona servidores
    home = str(Path.home())
    project = str(PROJECT_DIR)

    new_entries = {
        "filesystem": {
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                home,       # diretório home por padrão
                project,    # e o projeto atual
            ],
        },
        "browser": {
            "command": "npx",
            "args": ["-y", "@playwright/mcp", "--headless"],
        },
    }

    # Merge — não sobrescreve entradas existentes customizadas
    for key, val in new_entries.items():
        if key not in existing:
            existing[key] = val

    with open(MCP_CONFIG_PATH, "w") as f:
        json.dump(existing, f, indent=2)

    ok(f"MCP config escrito em {MCP_CONFIG_PATH}")
    info("MCP filesystem: acesso ao home e ao projeto (ajuste em ~/.claude/mcp.json)")
    info("MCP browser: Playwright headless ativado")


def step_smoke_test() -> bool:
    step("7/7 — Teste de fumaça")

    results = {}

    # Python imports
    # Módulos obrigatórios para o sistema funcionar
    required = {
        "sounddevice":    "Captura de áudio",
        "faster_whisper": "Transcrição (faster-whisper)",
        "numpy":          "NumPy",
        "yaml":           "PyYAML",
    }
    # Módulos opcionais (podem falhar em ambiente headless/CI)
    optional = {
        "pynput":    "Hotkey push-to-talk (pynput)",
        "pyperclip": "Clipboard (pyperclip)",
        "pyautogui": "Simulação de teclas (pyautogui)",
    }

    checks = {**required, **optional}

    for module, desc in checks.items():
        is_optional = module in optional
        try:
            __import__(module)
            ok(desc)
            results[module] = True
        except ImportError:
            if is_optional:
                warn(f"{desc} — não instalado (opcional, necessário no desktop)")
                results[module] = True  # não bloqueia o smoke test
            else:
                err(f"{desc} — não instalado")
                results[module] = False

    # TTS
    try:
        from TTS.api import TTS
        ok("Coqui TTS importado")
        results["TTS"] = True
    except ImportError:
        warn("Coqui TTS não instalado (opcional — rode com --skip-tts para ignorar)")
        results["TTS"] = False

    # Claude CLI
    if cmd_exists("claude"):
        ok("Claude Code CLI disponível")
        results["claude"] = True
    else:
        warn("Claude Code CLI não encontrado — respostas em voz não funcionarão")
        results["claude"] = False

    # Microfone
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devs = [d for d in devices if d["max_input_channels"] > 0]
        if input_devs:
            ok(f"Microfone detectado: {len(input_devs)} dispositivo(s)")
            results["microphone"] = True
        else:
            warn("Nenhum microfone detectado — conecte um microfone antes de usar")
            results["microphone"] = False
    except Exception as exc:
        warn(f"Erro ao verificar microfone: {exc}")
        results["microphone"] = False

    # Testes unitários
    info("Rodando testes unitários...")
    try:
        test_result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
            capture_output=True, text=True, cwd=str(PROJECT_DIR)
        )
        if test_result.returncode == 0:
            lines = test_result.stdout.strip().split("\n")
            summary = lines[-1] if lines else "ok"
            ok(f"Testes: {summary}")
            results["tests"] = True
        else:
            warn(f"Alguns testes falharam:\n{test_result.stdout[-500:]}")
            results["tests"] = False
    except Exception as exc:
        warn(f"Não foi possível rodar testes: {exc}")
        results["tests"] = False

    return all(results.get(k, False) for k in ["sounddevice", "faster_whisper", "numpy", "yaml"])


def step_print_summary(args):
    """Imprime resumo final e próximos passos."""
    step("Setup concluído!")

    print(f"""
{BOLD}Como usar:{RESET}

  {GREEN}python main.py{RESET}
      Pipeline completo: push-to-talk → transcrição → Claude Code → TTS

  {GREEN}python main.py --no-tts{RESET}
      Só entrada de voz (sem resposta em áudio)

  {GREEN}python main.py --list-devices{RESET}
      Lista microfones disponíveis

  {GREEN}python main.py --model base{RESET}
      Usa modelo Whisper mais leve (mais rápido, menos preciso)

{BOLD}Tecla padrão:{RESET} F9 (segurar para gravar, soltar para transcrever)

{BOLD}Personalizar:{RESET} edite config.yaml no projeto

{BOLD}TTS engine:{RESET} {'ElevenLabs' if args.tts == 'elevenlabs' else 'Coqui TTS (local)'}
""")

    if not cmd_exists("claude"):
        print(f"{YELLOW}  ATENÇÃO:{RESET} Claude Code não encontrado.")
        print(f"  Instale: npm install -g @anthropic-ai/claude-code")
        print(f"  Configure: claude auth\n")

    if args.tts == "elevenlabs":
        print(f"{YELLOW}  ElevenLabs:{RESET} configure a API key antes de usar:")
        print(f"  export ELEVENLABS_API_KEY=sua_key\n")


# ── Config update helper ─────────────────────────────────────────────────────────

def _update_config(section: str, key: str, value) -> None:
    """Atualiza um valor no config.yaml existente."""
    try:
        import yaml
        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}

        if section not in cfg:
            cfg[section] = {}
        cfg[section][key] = value

        with open(CONFIG_PATH, "w") as f:
            yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)
    except Exception as exc:
        warn(f"Não foi possível atualizar config.yaml: {exc}")


# ── Main ─────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Setup automático do Programador por Voz")
    p.add_argument("--skip-tts",  action="store_true", help="Pula download do modelo TTS")
    p.add_argument("--skip-mcp",  action="store_true", help="Pula instalação npm dos servidores MCP")
    p.add_argument("--tts",       default="coqui", choices=["coqui", "elevenlabs"], help="Engine de TTS")
    p.add_argument("--whisper-model", default="small",
                   choices=["tiny", "base", "small", "medium", "large-v3"],
                   help="Modelo Whisper a baixar")
    p.add_argument("--check",     action="store_true", help="Só verifica, não instala nada")
    return p.parse_args()


def main():
    args = parse_args()

    print(f"\n{BOLD}{'='*60}")
    print("  Programador por Voz — Setup Automático")
    print(f"{'='*60}{RESET}")
    print(f"  Sistema:  {SYSTEM} ({platform.machine()})")
    print(f"  Python:   {sys.version.split()[0]}")
    print(f"  Projeto:  {PROJECT_DIR}")
    print()

    if args.check:
        step_smoke_test()
        return

    steps = [
        ("Dependências Python",   lambda: step_python_deps(args)),
        ("Dependências sistema",  step_system_deps),
        ("Modelo Whisper",        lambda: step_download_whisper_model(args)),
        ("Modelo TTS",            lambda: step_download_tts_model(args)),
        ("Servidores MCP",        lambda: step_mcp_servers(args)),
        ("Configuração Claude",   lambda: step_configure_claude_code(args)),
        ("Teste de fumaça",       step_smoke_test),
    ]

    failed = []
    for name, fn in steps:
        try:
            ok_result = fn()
            if ok_result is False:
                failed.append(name)
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Setup interrompido pelo usuário.{RESET}")
            sys.exit(1)
        except Exception as exc:
            err(f"Etapa '{name}' falhou inesperadamente: {exc}")
            failed.append(name)

    step_print_summary(args)

    if failed:
        print(f"{YELLOW}Etapas com problemas:{RESET} {', '.join(failed)}")
        print("O sistema pode funcionar parcialmente. Veja os avisos acima.\n")
        sys.exit(1)
    else:
        print(f"{GREEN}{BOLD}Tudo pronto!{RESET} Execute: python main.py\n")


if __name__ == "__main__":
    main()
