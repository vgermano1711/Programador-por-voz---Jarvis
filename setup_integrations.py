#!/usr/bin/env python3
"""
J.A.R.V.I.S — Setup Automático de Integrações

Configura Spotify, GitHub e Google em sequência,
abrindo o browser nos lugares certos e salvando
as credenciais no keyring do sistema.
"""

import os
import sys
import time
import webbrowser
import subprocess
from pathlib import Path

# ── Cores no terminal ───────────────────────────────────────────────────────────
CYAN  = "\033[96m"
GREEN = "\033[92m"
YELLOW= "\033[93m"
RED   = "\033[91m"
BOLD  = "\033[1m"
RESET = "\033[0m"

def title(text):   print(f"\n{BOLD}{CYAN}{'='*60}{RESET}\n{BOLD}{CYAN}  {text}{RESET}\n{CYAN}{'='*60}{RESET}")
def ok(text):      print(f"  {GREEN}✓{RESET} {text}")
def warn(text):    print(f"  {YELLOW}⚠{RESET}  {text}")
def info(text):    print(f"  {CYAN}→{RESET} {text}")
def error(text):   print(f"  {RED}✗{RESET} {text}")
def ask(prompt):   return input(f"  {BOLD}>{RESET} {prompt}: ").strip()
def step(n, text): print(f"\n{BOLD}[{n}]{RESET} {text}")


def save_keyring(key: str, value: str, service: str = "jarvis") -> bool:
    try:
        import keyring
        keyring.set_password(service, key, value)
        return True
    except Exception as e:
        warn(f"keyring falhou ({e}), salvando em .env local")
        env_path = Path(".env.integrations")
        with open(env_path, "a") as f:
            f.write(f"{key.upper()}={value}\n")
        return False


def test_import(module: str) -> bool:
    try:
        __import__(module)
        return True
    except ImportError:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# SPOTIFY
# ─────────────────────────────────────────────────────────────────────────────

def setup_spotify():
    title("SPOTIFY — Controle de Música por Voz")
    print("""
  Com essa integração você poderá dizer ao Jarvis:
  • "toca Miles Davis"
  • "próxima música"
  • "volume 70"
  • "que música é essa?"
""")

    if not test_import("spotipy"):
        info("Instalando spotipy...")
        subprocess.run([sys.executable, "-m", "pip", "install", "spotipy", "-q"], check=True)
        ok("spotipy instalado")

    step(1, "Abrir o Spotify Developer Dashboard")
    info("Vou abrir o browser. Faça login com sua conta Spotify.")
    input("  Pressione Enter para abrir...")
    webbrowser.open("https://developer.spotify.com/dashboard")
    time.sleep(2)

    step(2, "Criar um App no Dashboard")
    print("""
  No Dashboard:
  1. Clique em "Create app"
  2. Nome: Jarvis
  3. Descrição: Jarvis Voice Assistant
  4. Redirect URI: http://localhost:8888/callback
  5. Marque "Web API" e clique em Save
""")
    input("  Pressione Enter quando o app estiver criado...")

    step(3, "Copiar as credenciais")
    info("Na página do app, clique em 'Settings' e copie:")

    client_id = ask("Client ID")
    if not client_id:
        warn("Client ID vazio — pulando Spotify")
        return False

    client_secret = ask("Client Secret")
    if not client_secret:
        warn("Client Secret vazio — pulando Spotify")
        return False

    save_keyring("jarvis_spotify_client_id", client_id)
    save_keyring("jarvis_spotify_client_secret", client_secret)

    # Testa a conexão
    step(4, "Testando conexão com Spotify")
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyPKCE
        sp = spotipy.Spotify(auth_manager=SpotifyPKCE(
            client_id=client_id,
            redirect_uri="http://localhost:8888/callback",
            scope="user-read-playback-state user-modify-playback-state user-read-currently-playing",
        ))
        info("Abrindo browser para autorizar o Jarvis no Spotify...")
        user = sp.current_user()
        ok(f"Conectado como: {user['display_name']}")
        return True
    except Exception as e:
        warn(f"Não foi possível testar agora ({e})")
        info("A autenticação será feita na primeira vez que você usar")
        return True


# ─────────────────────────────────────────────────────────────────────────────
# GITHUB
# ─────────────────────────────────────────────────────────────────────────────

def setup_github():
    title("GITHUB — Repositórios por Voz")
    print("""
  Com essa integração você poderá dizer ao Jarvis:
  • "quais são as PRs abertas?"
  • "últimos commits"
  • "cria issue: bug no login"
  • "resumo do repositório"
""")

    if not test_import("github"):
        info("Instalando PyGithub...")
        subprocess.run([sys.executable, "-m", "pip", "install", "PyGithub", "-q"], check=True)
        ok("PyGithub instalado")

    step(1, "Criar Personal Access Token no GitHub")
    info("Vou abrir o browser nas configurações do GitHub.")
    input("  Pressione Enter para abrir...")
    webbrowser.open("https://github.com/settings/tokens/new?scopes=repo,read:user&description=Jarvis+Voice+Assistant")
    time.sleep(2)

    step(2, "Gerar o token")
    print("""
  Na página que abriu:
  1. O nome já está preenchido como "Jarvis Voice Assistant"
  2. Os escopos "repo" e "read:user" já estão marcados
  3. Clique em "Generate token"
  4. COPIE o token agora (não aparece novamente)
""")

    token = ask("Token do GitHub (começa com 'ghp_')")
    if not token:
        warn("Token vazio — pulando GitHub")
        return False

    save_keyring("jarvis_github_token", token)

    # Testa
    step(3, "Testando conexão com GitHub")
    try:
        from github import Github
        g = Github(token)
        user = g.get_user()
        ok(f"Conectado como: {user.login}")
        repos = list(user.get_repos())[:3]
        info(f"Repositórios encontrados: {', '.join(r.name for r in repos)}")
        return True
    except Exception as e:
        error(f"Falha na conexão: {e}")
        warn("Verifique se o token está correto")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE (Calendar + Gmail)
# ─────────────────────────────────────────────────────────────────────────────

def setup_google():
    title("GOOGLE — Calendar e Gmail por Voz")
    print("""
  Com essa integração você poderá dizer ao Jarvis:
  • "o que tenho na agenda hoje?"
  • "próxima reunião"
  • "quantos emails não lidos?"
  • "últimos emails"
""")

    missing = []
    for pkg in ["google.auth", "google_auth_oauthlib", "googleapiclient"]:
        if not test_import(pkg):
            missing.append(pkg)

    if missing:
        info("Instalando bibliotecas do Google...")
        subprocess.run([
            sys.executable, "-m", "pip", "install",
            "google-auth", "google-auth-oauthlib", "google-api-python-client", "-q"
        ], check=True)
        ok("Bibliotecas Google instaladas")

    jarvis_dir = Path.home() / ".jarvis"
    jarvis_dir.mkdir(exist_ok=True)
    secret_path = jarvis_dir / "google_client_secret.json"

    step(1, "Criar projeto no Google Cloud Console")
    info("Vou abrir o browser no Google Cloud Console.")
    input("  Pressione Enter para abrir...")
    webbrowser.open("https://console.cloud.google.com/projectcreate")
    time.sleep(2)

    print("""
  No Google Cloud Console:
  1. Crie um projeto chamado "Jarvis"
  2. Selecione o projeto criado
""")
    input("  Pressione Enter quando o projeto estiver criado...")

    step(2, "Ativar as APIs necessárias")
    info("Abrindo ativação do Google Calendar API...")
    webbrowser.open("https://console.cloud.google.com/apis/library/calendar-json.googleapis.com")
    time.sleep(1)
    info("Abrindo ativação do Gmail API...")
    webbrowser.open("https://console.cloud.google.com/apis/library/gmail.googleapis.com")
    time.sleep(1)
    print("""
  Nas páginas que abriram:
  • Clique em "Ativar" em cada uma
""")
    input("  Pressione Enter quando as APIs estiverem ativadas...")

    step(3, "Criar credenciais OAuth2")
    webbrowser.open("https://console.cloud.google.com/apis/credentials/oauthclient")
    time.sleep(1)
    print("""
  Na página de credenciais:
  1. Tipo: "Aplicativo para computador"
  2. Nome: Jarvis
  3. Clique em "Criar"
  4. Clique em "Baixar JSON"
  5. Salve o arquivo como: google_client_secret.json
""")
    info(f"Mova o arquivo baixado para: {secret_path}")
    input("  Pressione Enter quando o arquivo estiver salvo...")

    if not secret_path.exists():
        # Tenta encontrar na pasta Downloads
        downloads = Path.home() / "Downloads"
        candidates = list(downloads.glob("client_secret*.json"))
        if candidates:
            import shutil
            shutil.copy(candidates[0], secret_path)
            ok(f"Arquivo copiado automaticamente de Downloads → {secret_path}")
        else:
            error(f"Arquivo não encontrado em {secret_path}")
            warn("Coloque o arquivo manualmente e rode o setup novamente")
            return False

    step(4, "Autorizar o Jarvis na sua conta Google")
    info("Abrindo browser para autorização OAuth...")
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        import pickle

        SCOPES = [
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
        ]

        flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), SCOPES)
        creds = flow.run_local_server(port=0)

        token_path = jarvis_dir / "google_credentials.json"
        with open(token_path, "w") as f:
            f.write(creds.to_json())

        ok(f"Token salvo em {token_path}")

        # Testa
        from googleapiclient.discovery import build
        service = build("calendar", "v3", credentials=creds)
        calendars = service.calendarList().list().execute()
        cal_names = [c["summary"] for c in calendars.get("items", [])[:3]]
        ok(f"Calendários encontrados: {', '.join(cal_names)}")
        return True

    except Exception as e:
        error(f"Falha na autorização: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print(f"""
{BOLD}{CYAN}
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
{RESET}
  Setup de Integrações — Spotify, GitHub e Google
""")

    results = {}

    integrations = [
        ("Spotify", setup_spotify),
        ("GitHub",  setup_github),
        ("Google",  setup_google),
    ]

    for name, fn in integrations:
        print(f"\n{YELLOW}Configurar {name}? (s/n){RESET} ", end="")
        choice = input().strip().lower()
        if choice in ("s", "sim", "y", "yes", ""):
            try:
                results[name] = fn()
            except KeyboardInterrupt:
                warn(f"\n{name} pulado.")
                results[name] = False
        else:
            info(f"{name} pulado.")
            results[name] = None

    # Resumo final
    title("RESUMO")
    for name, status in results.items():
        if status is True:
            ok(f"{name}: configurado com sucesso")
        elif status is False:
            warn(f"{name}: falhou ou incompleto")
        else:
            info(f"{name}: pulado")

    configured = [n for n, s in results.items() if s is True]
    if configured:
        print(f"""
{GREEN}{BOLD}  Integrações prontas: {', '.join(configured)}{RESET}

  Reinicie o Jarvis para ativar:
  {CYAN}py main.py{RESET}
""")
    else:
        print(f"""
  {YELLOW}Nenhuma integração configurada.{RESET}
  Rode este script novamente quando quiser configurar.
""")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Setup interrompido.{RESET}")
