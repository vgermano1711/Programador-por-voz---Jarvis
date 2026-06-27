"""
Configura o sistema de logging estruturado com suporte a arquivo rotativo e console.

Decisão de arquitetura: usamos logging padrão do Python (não structlog ou loguru)
para manter zero dependências extras e compatibilidade máxima. A formatação inclui
módulo + linha para facilitar debugging de falhas em produção.
"""

import logging
import logging.handlers
import os
import sys
from typing import Optional


_configured = False


def configure_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 3,
    console: bool = True,
) -> None:
    """Configura logging global. Deve ser chamado uma única vez na inicialização."""
    global _configured
    if _configured:
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    fmt = "%(asctime)s [%(levelname)-8s] %(name)s:%(lineno)d — %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=date_fmt)

    root = logging.getLogger()
    root.setLevel(numeric_level)

    if console:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        root.addHandler(handler)

    if log_file:
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # Silencia libs ruidosas em nível INFO
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)
    logging.getLogger("pystray").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger nomeado. Usar __name__ do módulo chamador."""
    return logging.getLogger(name)
