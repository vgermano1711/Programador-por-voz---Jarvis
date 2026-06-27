"""
Gerenciamento seguro de credenciais via keyring do sistema operacional.

Por que keyring e não .env?
- .env fica em disco em texto plano e pode ser acidentalmente commitado
- keyring usa o cofre nativo do SO: Keychain (macOS), Secret Service/KWallet (Linux),
  Windows Credential Manager — criptografados com senha do sistema
- Fallback para variável de ambiente se keyring não disponível (ex: servidor headless)

Instalação:
    pip install keyring

No Linux, pode precisar de:
    pip install secretstorage  # GNOME Keyring / KWallet
    # ou
    pip install keyrings.alt   # fallback em texto (menos seguro mas funciona)
"""

import os
from typing import Optional

from logging_setup import get_logger

logger = get_logger(__name__)

_SERVICE_NAME = "programador_por_voz"


def set_credential(name: str, value: str) -> bool:
    """
    Salva credencial no cofre do sistema.
    name: identificador (ex: "elevenlabs", "picovoice")
    """
    try:
        import keyring
        keyring.set_password(_SERVICE_NAME, name, value)
        logger.info("Credencial '%s' salva no keyring.", name)
        return True
    except ImportError:
        logger.warning("keyring não instalado. Instale: pip install keyring")
        return False
    except Exception as exc:
        logger.error("Falha ao salvar credencial '%s': %s", name, exc)
        return False


def get_credential(name: str) -> Optional[str]:
    """
    Recupera credencial do cofre do sistema.
    Retorna None se não encontrada.
    """
    # Variável de ambiente tem prioridade (útil em CI/CD ou Docker)
    env_key = f"{name.upper().replace('-', '_')}_API_KEY"
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val

    try:
        import keyring
        value = keyring.get_password(_SERVICE_NAME, name)
        return value
    except ImportError:
        return None
    except Exception as exc:
        logger.warning("Falha ao ler credencial '%s': %s", name, exc)
        return None


def delete_credential(name: str) -> bool:
    """Remove credencial do cofre."""
    try:
        import keyring
        keyring.delete_password(_SERVICE_NAME, name)
        logger.info("Credencial '%s' removida.", name)
        return True
    except Exception as exc:
        logger.warning("Falha ao remover credencial '%s': %s", name, exc)
        return False
