"""Valores padrão de configuração. Servem como fallback quando config.yaml não existe."""

DEFAULTS: dict = {
    "activation": {
        "mode": "push_to_talk",
        "push_to_talk_key": "f9",
        "wake_words": ["claude", "ei claude"],
        "wake_word_engine": "openwakeword",
        "porcupine_access_key": "",
    },
    "audio": {
        "device_index": None,
        "device_name": None,
        "sample_rate": 16000,
        "channels": 1,
        "chunk_duration_ms": 30,
        "max_recording_seconds": 30,
    },
    "transcription": {
        "model": "small",
        "device": "cpu",
        "compute_type": "int8",
        "language": "pt",
        "language_fallback": None,
        "language_confidence_threshold": 0.7,
        "beam_size": 5,
        "initial_prompt": "Código Python, terminal, programação em português.",
    },
    "vad": {
        "enabled": True,
        "aggressiveness": 2,
        "min_speech_duration_ms": 300,
        "silence_threshold_ms": 500,
    },
    "control_commands": {
        "cancela": ["cancela", "cancelar", "cancela isso"],
        "interrompe": ["interrompe", "interromper", "ctrl c", "para tudo"],
        "repete": ["repete", "repetir", "repete isso", "repete o último"],
        "limpa_tela": ["limpa tela", "limpar tela", "limpa o terminal"],
        "para": ["para", "parar"],
    },
    "injection": {
        "method": "clipboard",
        "auto_enter": True,
        "paste_delay_ms": 100,
        "valid_terminals": [
            "terminal", "konsole", "gnome-terminal", "xterm",
            "bash", "zsh", "fish", "cmd", "powershell",
            "windows terminal", "wt", "alacritty", "kitty",
            "iterm", "claude", "code",
        ],
    },
    "history": {
        "enabled": True,
        "file": "history.json",
        "max_entries": 1000,
    },
    "logging": {
        "level": "INFO",
        "file": "programador_por_voz.log",
        "max_file_size_mb": 10,
        "backup_count": 3,
        "console": True,
    },
    "ui": {
        "tray_enabled": True,
        "notifications": True,
    },
}
