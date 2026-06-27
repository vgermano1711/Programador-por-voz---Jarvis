"""
Gerenciador de servidores MCP (Model Context Protocol).

Cada servidor MCP roda como processo independente em background.
A falha de um servidor não afeta os demais nem o Claude Code básico.
O Claude Code detecta automaticamente servidores MCP via ~/.claude/mcp.json
ou via flags de linha de comando.

Servidores suportados:
  filesystem  — acesso a arquivos com whitelist explícita
  browser     — automação de browser via Playwright MCP
  (whatsapp e instagram documentados mas não implementados como código — ver abaixo)
"""

import json
import os
import subprocess
import threading
from typing import Optional

from logging_setup import get_logger

logger = get_logger(__name__)

_MCP_CONFIG_PATH = os.path.expanduser("~/.claude/mcp.json")


class MCPServerProcess:
    """Representa um processo de servidor MCP rodando em background."""

    def __init__(self, name: str, command: list[str], env: Optional[dict] = None) -> None:
        self.name = name
        self._command = command
        self._env = {**os.environ, **(env or {})}
        self._process: Optional[subprocess.Popen] = None
        self._log_thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        try:
            self._process = subprocess.Popen(
                self._command,
                env=self._env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            # Loga stderr em background para não perder mensagens de erro
            self._log_thread = threading.Thread(
                target=self._log_stderr,
                daemon=True,
                name=f"mcp-{self.name}-log",
            )
            self._log_thread.start()
            logger.info("Servidor MCP '%s' iniciado (pid=%d).", self.name, self._process.pid)
            return True
        except FileNotFoundError as exc:
            logger.error(
                "Servidor MCP '%s': comando não encontrado: %s\n"
                "Verifique se a dependência está instalada.",
                self.name, exc,
            )
            return False
        except Exception as exc:
            logger.error("Falha ao iniciar servidor MCP '%s': %s", self.name, exc)
            return False

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            logger.info("Servidor MCP '%s' encerrado.", self.name)

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _log_stderr(self) -> None:
        if self._process and self._process.stderr:
            for line in self._process.stderr:
                line = line.strip()
                if line:
                    logger.debug("[mcp:%s] %s", self.name, line)


class MCPManager:
    """
    Inicia, monitora e encerra servidores MCP configurados.

    Cada servidor é independente: se filesystem falhar, browser continua
    funcionando. Isso garante que o sistema de voz básico nunca quebre
    por falha de um servidor MCP periférico.
    """

    def __init__(self, cfg) -> None:
        self._cfg = cfg
        self._servers: dict[str, MCPServerProcess] = {}
        self._mcp_cfg_written = False

    def start_all(self) -> dict[str, bool]:
        """Inicia todos os servidores MCP habilitados. Retorna mapa de status."""
        results = {}

        if self._cfg.get("mcp", "filesystem", "enabled", default=False):
            results["filesystem"] = self._start_filesystem()

        if self._cfg.get("mcp", "browser", "enabled", default=False):
            results["browser"] = self._start_browser()

        # Persiste configuração para o Claude Code detectar os servidores
        if results:
            self._write_mcp_config()

        return results

    def stop_all(self) -> None:
        for server in self._servers.values():
            server.stop()

    def status(self) -> dict[str, bool]:
        return {name: srv.is_running() for name, srv in self._servers.items()}

    # ── Filesystem MCP ──────────────────────────────────────────────────────────

    def _start_filesystem(self) -> bool:
        """
        Inicia servidor MCP de filesystem com whitelist de diretórios.

        Usa @modelcontextprotocol/server-filesystem (Node.js).
        NUNCA permite acesso irrestrito ao disco — apenas diretórios explicitamente
        listados em mcp.filesystem.allowed_paths no config.yaml.
        """
        allowed_paths: list[str] = self._cfg.get(
            "mcp", "filesystem", "allowed_paths", default=[]
        )
        if not allowed_paths:
            logger.warning(
                "MCP filesystem: nenhum diretório em mcp.filesystem.allowed_paths. "
                "Configure os diretórios permitidos no config.yaml antes de habilitar."
            )
            return False

        # Expande ~ e valida que os diretórios existem
        resolved = []
        for path in allowed_paths:
            expanded = os.path.expanduser(path)
            if os.path.isdir(expanded):
                resolved.append(expanded)
            else:
                logger.warning("MCP filesystem: diretório '%s' não existe, ignorado.", path)

        if not resolved:
            logger.error("MCP filesystem: nenhum diretório válido configurado.")
            return False

        cmd = ["npx", "-y", "@modelcontextprotocol/server-filesystem"] + resolved
        server = MCPServerProcess("filesystem", cmd)
        started = server.start()
        if started:
            self._servers["filesystem"] = server
            logger.info("MCP filesystem: acesso permitido a %d diretório(s).", len(resolved))
        return started

    # ── Browser MCP ─────────────────────────────────────────────────────────────

    def _start_browser(self) -> bool:
        """
        Inicia servidor MCP de automação de browser via Playwright MCP.

        Usa @playwright/mcp (oficial da Microsoft/Playwright).
        Permite ao Claude Code: abrir URLs, ler conteúdo de página, preencher
        formulários, tirar screenshots.

        AVISO DE SEGURANÇA: toda ação que submete formulário ou clica em botão
        deve ser confirmada pelo usuário antes de executar (implementado via
        AuditLogger.log_external_action com confirmed=False + prompt ao usuário).
        """
        headless: bool = self._cfg.get("mcp", "browser", "headless", default=True)
        cmd = ["npx", "-y", "@playwright/mcp"]
        if headless:
            cmd.append("--headless")

        server = MCPServerProcess("browser", cmd)
        started = server.start()
        if started:
            self._servers["browser"] = server
            logger.info(
                "MCP browser: Playwright MCP iniciado (headless=%s).", headless
            )
        return started

    # ── Config Claude Code ──────────────────────────────────────────────────────

    def _write_mcp_config(self) -> None:
        """
        Escreve/atualiza ~/.claude/mcp.json para que o Claude Code descubra
        os servidores MCP automaticamente.
        """
        try:
            os.makedirs(os.path.dirname(_MCP_CONFIG_PATH), exist_ok=True)

            existing = {}
            if os.path.exists(_MCP_CONFIG_PATH):
                with open(_MCP_CONFIG_PATH, "r", encoding="utf-8") as f:
                    existing = json.load(f)

            # Adiciona servidores rodando
            for name, server in self._servers.items():
                if server.is_running():
                    existing[name] = {
                        "command": server._command[0],
                        "args": server._command[1:],
                    }

            with open(_MCP_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)

            logger.info("Configuração MCP escrita em %s.", _MCP_CONFIG_PATH)
        except Exception as exc:
            logger.error("Falha ao escrever mcp.json: %s", exc)
