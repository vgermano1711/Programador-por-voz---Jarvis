import os
import re
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from github import Github
    _PYGITHUB_AVAILABLE = True
except ImportError:
    _PYGITHUB_AVAILABLE = False


def _get_token() -> Optional[str]:
    value = os.environ.get("GITHUB_TOKEN")
    if value:
        return value
    try:
        import keyring
        return keyring.get_password("jarvis", "jarvis_github_token")
    except Exception:
        return None


def _get_current_repo_remote() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _parse_repo_name(remote_url: str) -> Optional[str]:
    match = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", remote_url)
    if match:
        return match.group(1)
    return None


def _get_current_branch() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


class GitHubIntegration:
    def __init__(self) -> None:
        self._gh: Optional["Github"] = None
        self._repo = None
        self._init_attempted = False

    def _get_repo(self):
        if self._init_attempted:
            return self._repo
        self._init_attempted = True
        if not _PYGITHUB_AVAILABLE:
            logger.warning("PyGithub não instalado. Execute: pip install PyGithub")
            return None
        token = _get_token()
        if not token:
            logger.warning("GitHub: token não encontrado (keyring 'jarvis_github_token' ou env GITHUB_TOKEN).")
            return None
        remote_url = _get_current_repo_remote()
        if not remote_url:
            logger.warning("GitHub: não foi possível detectar remote origin.")
            return None
        repo_name = _parse_repo_name(remote_url)
        if not repo_name:
            logger.warning("GitHub: não foi possível parsear repo de '%s'.", remote_url)
            return None
        try:
            self._gh = Github(token)
            self._repo = self._gh.get_repo(repo_name)
        except Exception as exc:
            logger.warning("GitHub: falha ao conectar ao repo '%s': %s", repo_name, exc)
            self._repo = None
        return self._repo

    def is_available(self) -> bool:
        if not _PYGITHUB_AVAILABLE:
            return False
        if not _get_token():
            return False
        return bool(_get_current_repo_remote())

    def get_open_prs(self) -> str:
        repo = self._get_repo()
        if repo is None:
            return "GitHub indisponível."
        try:
            prs = list(repo.get_pulls(state="open"))
            if not prs:
                return "Nenhuma PR aberta."
            lines = [f"#{pr.number} {pr.title} (@{pr.user.login})" for pr in prs]
            return f"{len(prs)} PR(s) abertas:\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("GitHub get_open_prs falhou: %s", exc)
            return "Erro ao buscar PRs."

    def get_issues(self, state: str = "open") -> str:
        repo = self._get_repo()
        if repo is None:
            return "GitHub indisponível."
        try:
            issues = [i for i in repo.get_issues(state=state) if i.pull_request is None]
            if not issues:
                return f"Nenhuma issue {state}."
            lines = [f"#{i.number} {i.title} (@{i.user.login})" for i in issues]
            return f"{len(issues)} issue(s) {state}:\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("GitHub get_issues falhou: %s", exc)
            return "Erro ao buscar issues."

    def get_recent_commits(self, limit: int = 5) -> str:
        repo = self._get_repo()
        if repo is None:
            return "GitHub indisponível."
        branch = _get_current_branch() or repo.default_branch
        try:
            commits = list(repo.get_commits(sha=branch))[:limit]
            if not commits:
                return "Nenhum commit encontrado."
            lines = [
                f"{c.sha[:7]} {c.commit.message.splitlines()[0]} ({c.commit.author.name})"
                for c in commits
            ]
            return f"Últimos {len(commits)} commits em '{branch}':\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("GitHub get_recent_commits falhou: %s", exc)
            return "Erro ao buscar commits."

    def create_issue(self, title: str, body: str = "") -> str:
        repo = self._get_repo()
        if repo is None:
            return "GitHub indisponível."
        try:
            issue = repo.create_issue(title=title, body=body)
            return issue.html_url
        except Exception as exc:
            logger.warning("GitHub create_issue falhou: %s", exc)
            return "Erro ao criar issue."

    def get_repo_summary(self) -> str:
        repo = self._get_repo()
        if repo is None:
            return "GitHub indisponível."
        try:
            branch = _get_current_branch() or repo.default_branch
            last_commit = list(repo.get_commits(sha=branch))[:1]
            last_msg = last_commit[0].commit.message.splitlines()[0] if last_commit else "N/A"
            return (
                f"Repositório: {repo.full_name}\n"
                f"Stars: {repo.stargazers_count}\n"
                f"Branch atual: {branch}\n"
                f"Último commit: {last_msg}"
            )
        except Exception as exc:
            logger.warning("GitHub get_repo_summary falhou: %s", exc)
            return "Erro ao buscar resumo do repositório."

    def handle_voice_command(self, text: str) -> Optional[str]:
        text_lower = text.lower().strip()

        if any(p in text_lower for p in ("prs abertas", "pull requests", "minhas pull requests", "quais são as prs")):
            return self.get_open_prs()

        if any(p in text_lower for p in ("quais são as issues", "problemas abertos", "issues abertas")):
            return self.get_issues()

        if any(p in text_lower for p in ("últimos commits", "ultimos commits", "o que foi commitado")):
            return self.get_recent_commits()

        if any(p in text_lower for p in ("resumo do repositório", "resumo do repositorio", "status do projeto")):
            return self.get_repo_summary()

        match = re.match(r"cria\s+issue\s+(.+)", text_lower)
        if match:
            title = match.group(1).strip()
            url = self.create_issue(title=title)
            return f"Issue criada: {url}"

        return None
