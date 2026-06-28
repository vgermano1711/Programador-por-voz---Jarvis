"""
Diagnóstico de hotkey — testa exatamente o mesmo código do main.py.
Execute: py test_hotkey.py
Pressione F8 (ou a tecla configurada) e veja o resultado.
"""
import sys
sys.path.insert(0, ".")
from pynput import keyboard as kb
from config import load_config

cfg = load_config()
ptk_key = cfg.get("activation", "push_to_talk_key", default="f8")
print(f"Tecla configurada no config.yaml: {ptk_key!r}")

# Replica _parse_key do capture.py
key_str = ptk_key.strip().strip('"').strip("'").lower()
special = {
    "f1": kb.Key.f1, "f2": kb.Key.f2, "f3": kb.Key.f3, "f4": kb.Key.f4,
    "f5": kb.Key.f5, "f6": kb.Key.f6, "f7": kb.Key.f7, "f8": kb.Key.f8,
    "f9": kb.Key.f9, "f10": kb.Key.f10, "f11": kb.Key.f11, "f12": kb.Key.f12,
    "shift": kb.Key.shift, "shift_l": kb.Key.shift_l, "shift_r": kb.Key.shift_r,
    "right_shift": kb.Key.shift_r, "left_shift": kb.Key.shift_l,
    "ctrl": kb.Key.ctrl, "ctrl_l": kb.Key.ctrl_l, "ctrl_r": kb.Key.ctrl_r,
    "left_ctrl": kb.Key.ctrl_l, "right_ctrl": kb.Key.ctrl_r,
    "alt": kb.Key.alt, "alt_l": kb.Key.alt_l, "alt_r": kb.Key.alt_r,
    "left_alt": kb.Key.alt_l, "right_alt": kb.Key.alt_r,
    "tab": kb.Key.tab, "space": kb.Key.space,
    "esc": kb.Key.esc, "enter": kb.Key.enter,
    "scroll_lock": kb.Key.scroll_lock, "pause": kb.Key.pause,
    "caps_lock": kb.Key.caps_lock, "print_screen": kb.Key.print_screen,
    "insert": kb.Key.insert, "delete": kb.Key.delete,
    "home": kb.Key.home, "end": kb.Key.end,
    "page_up": kb.Key.page_up, "page_down": kb.Key.page_down,
}
target_key = special.get(key_str) or kb.KeyCode.from_char(key_str)
alt_keys = {kb.Key.alt, kb.Key.alt_l, kb.Key.alt_r}
ctrl_keys = {kb.Key.ctrl, kb.Key.ctrl_l, kb.Key.ctrl_r}
shift_keys = {kb.Key.shift, kb.Key.shift_l, kb.Key.shift_r}
modifier_groups = [alt_keys, ctrl_keys, shift_keys]
target_group = next((g for g in modifier_groups if target_key in g), {target_key})

print(f"Objeto pynput da tecla: {target_key}")
print(f"Grupo de detecção: {target_group}")
print()
print("Pressione a tecla configurada e solte. Ctrl+C para sair.")
print("-" * 50)

def on_press(key):
    match = key in target_group
    print(f"PRESSIONOU: {key!r}  |  match={match}")
    if match:
        print("  >>> TECLA CORRETA — gravação iniciaria aqui <<<")

def on_release(key):
    match = key in target_group
    print(f"SOLTOU:     {key!r}  |  match={match}")
    if match:
        print("  >>> TECLA CORRETA — gravação pararia aqui <<<")

with kb.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()
