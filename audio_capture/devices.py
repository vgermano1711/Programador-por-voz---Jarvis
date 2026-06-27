"""
Enumera e seleciona dispositivos de microfone usando sounddevice.

Permite seleção por índice numérico ou por substring do nome — a config salva
o índice (mais estável) ou o nome (mais legível). Na inicialização, tentamos
resolver nome→índice para compatibilidade entre sistemas.
"""

from typing import Optional
import sounddevice as sd

from logging_setup import get_logger

logger = get_logger(__name__)


def list_microphones() -> list[dict]:
    """Retorna lista de dispositivos de entrada disponíveis."""
    devices = []
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            devices.append({
                "index": idx,
                "name": dev["name"],
                "channels": dev["max_input_channels"],
                "sample_rate": int(dev["default_samplerate"]),
                "hostapi": sd.query_hostapis(dev["hostapi"])["name"],
            })
    return devices


def print_microphones() -> None:
    """Imprime tabela formatada de microfones para seleção interativa."""
    mics = list_microphones()
    if not mics:
        print("Nenhum microfone detectado.")
        return
    print(f"\n{'Idx':>4}  {'Nome':<45}  {'Ch':>3}  {'Hz':>7}  API")
    print("-" * 75)
    for mic in mics:
        print(
            f"{mic['index']:>4}  {mic['name']:<45}  "
            f"{mic['channels']:>3}  {mic['sample_rate']:>7}  {mic['hostapi']}"
        )
    print()


def select_device(
    device_index: Optional[int] = None,
    device_name: Optional[str] = None,
) -> Optional[int]:
    """
    Resolve índice final do dispositivo.
    Prioridade: device_index > device_name > padrão do sistema (None).
    """
    if device_index is not None:
        try:
            dev = sd.query_devices(device_index)
            if dev["max_input_channels"] > 0:
                logger.info("Usando microfone #%d: %s", device_index, dev["name"])
                return device_index
            logger.warning("Dispositivo #%d não tem canais de entrada.", device_index)
        except Exception as exc:
            logger.warning("Índice de dispositivo inválido (%s): %s", device_index, exc)

    if device_name:
        name_lower = device_name.lower()
        for mic in list_microphones():
            if name_lower in mic["name"].lower():
                logger.info(
                    "Microfone '%s' resolvido para índice #%d", device_name, mic["index"]
                )
                return mic["index"]
        logger.warning("Microfone com nome '%s' não encontrado.", device_name)

    logger.info("Usando dispositivo de entrada padrão do sistema.")
    return None
