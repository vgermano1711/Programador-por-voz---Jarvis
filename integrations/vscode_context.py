from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_JARVIS_DIR = Path.home() / ".jarvis"
_ACTIVE_FILE_TXT = _JARVIS_DIR / "vscode_active_file.txt"

_LANG_MAP: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript React",
    ".jsx": "JavaScript React",
    ".java": "Java",
    ".c": "C",
    ".cpp": "C++",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".md": "Markdown",
    ".sh": "Shell",
    ".bash": "Bash",
    ".sql": "SQL",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".dart": "Dart",
    ".r": "R",
    ".toml": "TOML",
    ".xml": "XML",
}

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False


def _detect_language(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return _LANG_MAP.get(suffix, "Texto")


def _find_via_psutil() -> Optional[str]:
    if not _PSUTIL_AVAILABLE:
        return None
    try:
        for proc in psutil.process_iter(["name", "cmdline"]):
            name = (proc.info.get("name") or "").lower()
            if "code" not in name:
                continue
            cmdline = proc.info.get("cmdline") or []
            for arg in cmdline:
                p = Path(arg)
                if p.is_file() and p.suffix in _LANG_MAP:
                    return str(p.resolve())
    except Exception:
        pass
    return None


class VSCodeContext:
    def get_active_file(self) -> Optional[str]:
        env_val = os.environ.get("VSCODE_ACTIVE_FILE")
        if env_val and Path(env_val).is_file():
            return env_val

        if _ACTIVE_FILE_TXT.exists():
            try:
                content = _ACTIVE_FILE_TXT.read_text(encoding="utf-8").strip()
                if content and Path(content).is_file():
                    return content
            except Exception:
                pass

        psutil_result = _find_via_psutil()
        if psutil_result:
            return psutil_result

        return None

    def get_active_file_content(self, max_lines: int = 100) -> Optional[str]:
        path = self.get_active_file()
        if path is None:
            return None
        try:
            lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
            return "\n".join(lines[:max_lines])
        except Exception:
            return None

    def get_active_file_summary(self) -> Optional[str]:
        path = self.get_active_file()
        if path is None:
            return None
        try:
            p = Path(path)
            lang = _detect_language(path)
            total_lines = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
            return f"Arquivo: {p.name} ({lang}, {total_lines} linhas)"
        except Exception:
            return None

    def set_active_file(self, path: str) -> None:
        _JARVIS_DIR.mkdir(parents=True, exist_ok=True)
        _ACTIVE_FILE_TXT.write_text(path, encoding="utf-8")

    def get_context_for_prompt(self) -> str:
        path = self.get_active_file()
        if path is None:
            return ""
        try:
            p = Path(path)
            lang = _detect_language(path)
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            total = len(lines)
            preview = "\n".join(lines[:50])
            return (
                f"Arquivo ativo no VS Code: {p.name}\n"
                f"Linguagem: {lang}\n"
                f"Total de linhas: {total}\n"
                f"Primeiras 50 linhas:\n```\n{preview}\n```"
            )
        except Exception:
            return ""
