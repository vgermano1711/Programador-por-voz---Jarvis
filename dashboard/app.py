import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from logging_setup import get_logger

logger = get_logger(__name__)

_AUDIT_LOG = "audit_log.jsonl"
_MEMORIES_DB = "memories.db"
_MAX_CONVERSATIONS = 50

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Jarvis Dashboard</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0a0a0a; color: #c0c0c0; font-family: 'Courier New', monospace; padding: 24px; }}
  h1 {{ color: #00ffcc; font-size: 1.6rem; letter-spacing: 4px; text-transform: uppercase; margin-bottom: 8px; }}
  .subtitle {{ color: #006644; font-size: 0.75rem; letter-spacing: 2px; margin-bottom: 28px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }}
  .card {{ background: #111; border: 1px solid #00ffcc33; border-radius: 4px; padding: 16px; }}
  .card-label {{ color: #00ffcc88; font-size: 0.7rem; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 8px; }}
  .card-value {{ color: #00ffcc; font-size: 2rem; font-weight: bold; }}
  .status-badge {{ display: inline-block; padding: 4px 12px; border-radius: 2px; font-size: 0.75rem; letter-spacing: 2px; text-transform: uppercase; }}
  .status-idle {{ border: 1px solid #00ffcc55; color: #00ffcc; }}
  .status-recording {{ border: 1px solid #ff4444; color: #ff4444; animation: pulse 1s infinite; }}
  .status-processing {{ border: 1px solid #ffaa00; color: #ffaa00; }}
  @keyframes pulse {{ 0%,100% {{ opacity:1 }} 50% {{ opacity:0.4 }} }}
  h2 {{ color: #00ffcc; font-size: 0.9rem; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 12px; border-bottom: 1px solid #00ffcc22; padding-bottom: 8px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
  th {{ color: #00ffcc88; text-align: left; padding: 6px 8px; border-bottom: 1px solid #00ffcc22; font-weight: normal; letter-spacing: 1px; text-transform: uppercase; }}
  td {{ padding: 6px 8px; border-bottom: 1px solid #111; color: #aaa; vertical-align: top; }}
  td:first-child {{ color: #555; white-space: nowrap; }}
  td.type {{ color: #00ffcc88; }}
  td.content {{ max-width: 500px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  tr:hover td {{ background: #111; }}
  .footer {{ margin-top: 24px; color: #333; font-size: 0.7rem; text-align: center; }}
</style>
<script>
  setTimeout(function(){{ window.location.reload(); }}, 5000);
</script>
</head>
<body>
<h1>&#9670; Jarvis</h1>
<div class="subtitle">Sistema de Programacao por Voz — Dashboard</div>
<div class="grid">
  <div class="card">
    <div class="card-label">Status</div>
    <div class="card-value">
      <span class="status-badge status-{status_class}">{status}</span>
    </div>
  </div>
  <div class="card">
    <div class="card-label">Interacoes hoje</div>
    <div class="card-value">{today_count}</div>
  </div>
  <div class="card">
    <div class="card-label">Total no log</div>
    <div class="card-value">{total_count}</div>
  </div>
  <div class="card">
    <div class="card-label">Ultima atividade</div>
    <div class="card-value" style="font-size:1rem;padding-top:8px">{last_activity}</div>
  </div>
</div>
<h2>Conversas Recentes</h2>
<table>
  <thead><tr><th>Hora</th><th>Tipo</th><th>Conteudo</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
<div class="footer">Auto-refresh a cada 5s &mdash; {now}</div>
</body>
</html>"""


def _load_audit_entries(limit: int = _MAX_CONVERSATIONS) -> list[dict]:
    entries: list[dict] = []
    if not os.path.exists(_AUDIT_LOG):
        return entries
    try:
        with open(_AUDIT_LOG, "r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entries.append(json.loads(raw))
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    return entries[-limit:]


def _count_today(entries: list[dict]) -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    return sum(1 for e in entries if e.get("timestamp", "").startswith(today))


def _fmt_time(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts).strftime("%H:%M:%S")
    except Exception:
        return ts[:8] if ts else ""


class DashboardServer:
    """Servidor web leve para monitoramento do sistema Jarvis."""

    def __init__(self) -> None:
        self._status: str = "idle"
        self._server: Any = None
        self._thread: Optional[threading.Thread] = None

    def update_status(self, status: str) -> None:
        self._status = status

    def start(self, port: int = 7432) -> None:
        try:
            from flask import Flask, jsonify, Response
        except ImportError:
            logger.warning("Flask não instalado — dashboard web desativado. Instale com: pip install flask")
            return

        app = Flask(__name__)
        server_ref = self

        @app.route("/")
        def index() -> Response:
            entries = _load_audit_entries()
            today_count = _count_today(entries)
            last_ts = entries[-1].get("timestamp", "") if entries else ""
            last_activity = _fmt_time(last_ts) if last_ts else "—"

            rows_html = ""
            for e in reversed(entries):
                ts = _fmt_time(e.get("timestamp", ""))
                etype = e.get("event_type", "")
                content = e.get("content", "")
                content_escaped = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                rows_html += f"<tr><td>{ts}</td><td class='type'>{etype}</td><td class='content' title='{content_escaped}'>{content_escaped}</td></tr>"

            status = server_ref._status
            status_class = status if status in ("idle", "recording", "processing") else "idle"
            html = _HTML_TEMPLATE.format(
                status=status,
                status_class=status_class,
                today_count=today_count,
                total_count=len(entries),
                last_activity=last_activity,
                rows=rows_html,
                now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            return Response(html, mimetype="text/html")

        @app.route("/api/status")
        def api_status() -> Response:
            return jsonify({"status": server_ref._status, "timestamp": datetime.now().isoformat()})

        @app.route("/api/conversations")
        def api_conversations() -> Response:
            return jsonify(_load_audit_entries())

        @app.route("/api/memories")
        def api_memories() -> Response:
            memories: list[dict] = []
            if os.path.exists(_MEMORIES_DB):
                try:
                    import sqlite3
                    with sqlite3.connect(_MEMORIES_DB) as conn:
                        conn.row_factory = sqlite3.Row
                        rows = conn.execute("SELECT * FROM memories ORDER BY created_at DESC LIMIT 100").fetchall()
                        memories = [dict(r) for r in rows]
                except Exception as exc:
                    logger.debug("Erro ao ler memories.db: %s", exc)
            return jsonify(memories)

        def _run() -> None:
            try:
                import logging as _logging
                log = _logging.getLogger("werkzeug")
                log.setLevel(_logging.ERROR)
                app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
            except Exception as exc:
                logger.error("Erro no servidor dashboard: %s", exc)

        self._thread = threading.Thread(target=_run, daemon=True, name="dashboard-server")
        self._thread.start()
        logger.info("Dashboard web iniciado em http://127.0.0.1:%d", port)

    def stop(self) -> None:
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass
        logger.info("DashboardServer parado.")
