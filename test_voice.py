"""
Diagnóstico rápido: testa Claude → TTS → áudio sem precisar do hotkey.
Execute: py test_voice.py
"""
import sys, time
sys.path.insert(0, ".")

from config import load_config
from response_capture.claude_subprocess import ClaudeCapture
from tts.edge_engine import EdgeTTSEngine
from tts.player import AudioPlayer

cfg = load_config()

print("=" * 50)
print("1. Testando Claude...")
cc = ClaudeCapture(cfg)
response = cc.send("responda apenas com uma frase curta: confirme que está operacional, me chame de Victor.")
print(f"   Claude respondeu: {repr(response[:120] if response else None)}")

if not response:
    print("\n   ERRO: Claude não respondeu. Verifique se 'claude' está no PATH.")
    print("   Teste manual: claude --print 'olá'")
    sys.exit(1)

print("\n2. Testando TTS (edge-tts)...")
engine = EdgeTTSEngine()
audio = engine.synthesize(response[:300])
print(f"   Áudio gerado: {len(audio)} bytes")

if not audio:
    print("\n   ERRO: TTS não gerou áudio. Verifique internet e edge-tts.")
    sys.exit(1)

print("\n3. Reproduzindo áudio... (você deve ouvir o Jarvis agora)")
player = AudioPlayer(sample_rate=24000)
player.play(audio)
player.wait(timeout=15)

print("\nDiagnóstico concluído. Se ouviu a voz, o sistema funciona.")
print("Se não ouviu, o problema é no dispositivo de áudio de saída.")
