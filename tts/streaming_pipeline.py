"""
Pipeline TTS em streaming: sintetiza frase a frase enquanto a resposta ainda chega.

Fluxo:
  chunks de texto → extrator de frases → síntese TTS → playback sequencial

A sobreposição acontece assim:
  t=0   Claude começa a responder
  t=0.3 Primeira frase completa → síntese TTS começa
  t=0.8 Áudio da frase 1 pronto → reprodução começa
  t=0.9 Frase 2 completa → síntese da frase 2 começa (enquanto frase 1 toca)
  t=1.4 Frase 1 termina → frase 2 começa a tocar imediatamente
  ...

Latência percebida = latência_claude_primeira_frase + latência_tts_uma_frase
Tipicamente: ~400ms (Claude) + ~400ms (edge-tts) = ~800ms até o primeiro som.

Nota sobre "tempo real": o pipeline não tem latência zero — isso é limite físico
de qualquer sistema voz→IA→voz. O objetivo é "fluido e rápido", não instantâneo.
"""

import queue
import re
import threading
from typing import Callable, Iterator, Optional

from logging_setup import get_logger

logger = get_logger(__name__)

_MIN_SENTENCE_CHARS = 15  # evita sintetizar fragmentos muito curtos


class StreamingTTSPipeline:
    """
    Conecta um iterador de texto (chunks do Claude) a um TTS engine
    com sobreposição de síntese e playback.

    Uso:
        pipeline = StreamingTTSPipeline(tts_engine, audio_player)
        pipeline.stream(chunk_iterator)   # bloqueia até terminar
        pipeline.stop()                   # interrompe imediatamente (thread-safe)
    """

    def __init__(self, tts_engine, audio_player) -> None:
        self._engine = tts_engine
        self._player = audio_player
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """Para síntese e playback imediatamente."""
        self._stop_event.set()
        self._player.stop()

    def stream(
        self,
        text_iterator: Iterator[str],
        on_sentence: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Consome chunks de texto, extrai frases e reproduz em streaming.
        Bloqueia até o fim ou stop() ser chamado.

        Args:
            text_iterator: produz pedaços de texto (linhas do Claude)
            on_sentence: callback opcional com cada frase antes de sintetizar
        """
        self._stop_event.clear()

        # Fila de frases (str) e fila de áudio (bytes). maxsize evita acúmulo excessivo.
        sentence_q: queue.Queue = queue.Queue()
        audio_q: queue.Queue = queue.Queue(maxsize=2)

        feeder = threading.Thread(
            target=self._feed_sentences,
            args=(text_iterator, sentence_q),
            daemon=True,
            name="tts-feeder",
        )
        synth = threading.Thread(
            target=self._synthesis_worker,
            args=(sentence_q, audio_q, on_sentence),
            daemon=True,
            name="tts-synth",
        )
        player = threading.Thread(
            target=self._playback_worker,
            args=(audio_q,),
            daemon=True,
            name="tts-play",
        )

        feeder.start()
        synth.start()
        player.start()

        feeder.join()
        synth.join()
        player.join()

    # ── Workers internos ─────────────────────────────────────────────────────────

    def _feed_sentences(self, text_iterator: Iterator[str], out_q: queue.Queue) -> None:
        buffer = ""
        try:
            for chunk in text_iterator:
                if self._stop_event.is_set():
                    break
                buffer += chunk
                sentences, buffer = self._split_sentences(buffer)
                for s in sentences:
                    if self._stop_event.is_set():
                        break
                    out_q.put(s)
            if buffer.strip() and not self._stop_event.is_set():
                out_q.put(buffer.strip())
        except Exception as exc:
            logger.error("Feeder erro: %s", exc)
        finally:
            out_q.put(None)

    def _synthesis_worker(
        self,
        in_q: queue.Queue,
        out_q: queue.Queue,
        on_sentence: Optional[Callable],
    ) -> None:
        try:
            while not self._stop_event.is_set():
                sentence = in_q.get()
                if sentence is None:
                    break
                if on_sentence:
                    try:
                        on_sentence(sentence)
                    except Exception:
                        pass
                try:
                    audio = self._engine.synthesize(sentence)
                    if audio:
                        out_q.put(audio)
                except Exception as exc:
                    logger.error("Síntese TTS erro: %s", exc)
        finally:
            out_q.put(None)

    def _playback_worker(self, in_q: queue.Queue) -> None:
        try:
            while not self._stop_event.is_set():
                audio = in_q.get()
                if audio is None:
                    break
                self._player.play(audio)
                self._player.wait()  # espera essa frase terminar antes da próxima
        except Exception as exc:
            logger.error("Playback erro: %s", exc)

    # ── Extração de frases ───────────────────────────────────────────────────────

    @staticmethod
    def _split_sentences(text: str) -> tuple:
        """
        Divide texto em frases completas, deixando fragmentos incompletos no buffer.
        Retorna (lista_de_frases_completas, buffer_restante).
        """
        sentences: list[str] = []
        # Divide nos pontos de quebra naturais seguidos de espaço
        parts = re.split(r'(?<=[.!?;])\s+', text)
        for part in parts[:-1]:
            part = part.strip()
            if not part:
                continue
            # Remove markdown inline que sobrou (**, *, `, #)
            part = re.sub(r'[*#`_]+', '', part).strip()
            if len(part) >= _MIN_SENTENCE_CHARS:
                sentences.append(part)
            elif sentences:
                sentences[-1] += " " + part
        return sentences, parts[-1] if parts else ""
