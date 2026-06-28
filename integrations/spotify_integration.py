import os
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import spotipy
    from spotipy.oauth2 import SpotifyPKCE
    _SPOTIPY_AVAILABLE = True
except ImportError:
    _SPOTIPY_AVAILABLE = False


def _get_credential(keyring_key: str, env_var: str) -> Optional[str]:
    value = os.environ.get(env_var)
    if value:
        return value
    try:
        import keyring
        return keyring.get_password("jarvis", keyring_key)
    except Exception:
        return None


class SpotifyIntegration:
    SCOPE = (
        "user-read-playback-state "
        "user-modify-playback-state "
        "user-read-currently-playing"
    )

    def __init__(self) -> None:
        self._client: Optional["spotipy.Spotify"] = None
        self._init_attempted = False

    def _get_client(self) -> Optional["spotipy.Spotify"]:
        if self._init_attempted:
            return self._client
        self._init_attempted = True
        if not _SPOTIPY_AVAILABLE:
            logger.warning("spotipy não instalado. Execute: pip install spotipy")
            return None
        client_id = _get_credential("jarvis_spotify_client_id", "SPOTIFY_CLIENT_ID")
        client_secret = _get_credential("jarvis_spotify_client_secret", "SPOTIFY_CLIENT_SECRET")
        if not client_id:
            logger.warning("Spotify: client_id não encontrado.")
            return None
        try:
            auth = SpotifyPKCE(
                client_id=client_id,
                redirect_uri="http://localhost:8888/callback",
                scope=self.SCOPE,
            )
            self._client = spotipy.Spotify(auth_manager=auth)
        except Exception as exc:
            logger.warning("Spotify: falha na autenticação: %s", exc)
            self._client = None
        return self._client

    def is_available(self) -> bool:
        if not _SPOTIPY_AVAILABLE:
            return False
        client_id = _get_credential("jarvis_spotify_client_id", "SPOTIFY_CLIENT_ID")
        return bool(client_id)

    def play(self, query: str = None) -> None:
        sp = self._get_client()
        if sp is None:
            logger.warning("Spotify indisponível.")
            return
        try:
            if query:
                results = sp.search(q=query, limit=1, type="track,playlist,artist")
                uri = None
                for kind in ("tracks", "playlists", "artists"):
                    items = results.get(kind, {}).get("items", [])
                    if items:
                        uri = items[0]["uri"]
                        break
                if uri:
                    if uri.startswith("spotify:track"):
                        sp.start_playback(uris=[uri])
                    else:
                        sp.start_playback(context_uri=uri)
                else:
                    logger.warning("Spotify: nenhum resultado para '%s'.", query)
            else:
                sp.start_playback()
        except Exception as exc:
            logger.warning("Spotify play falhou: %s", exc)

    def pause(self) -> None:
        sp = self._get_client()
        if sp is None:
            logger.warning("Spotify indisponível.")
            return
        try:
            sp.pause_playback()
        except Exception as exc:
            logger.warning("Spotify pause falhou: %s", exc)

    def next_track(self) -> None:
        sp = self._get_client()
        if sp is None:
            logger.warning("Spotify indisponível.")
            return
        try:
            sp.next_track()
        except Exception as exc:
            logger.warning("Spotify next_track falhou: %s", exc)

    def previous_track(self) -> None:
        sp = self._get_client()
        if sp is None:
            logger.warning("Spotify indisponível.")
            return
        try:
            sp.previous_track()
        except Exception as exc:
            logger.warning("Spotify previous_track falhou: %s", exc)

    def set_volume(self, percent: int) -> None:
        sp = self._get_client()
        if sp is None:
            logger.warning("Spotify indisponível.")
            return
        percent = max(0, min(100, percent))
        try:
            sp.volume(percent)
        except Exception as exc:
            logger.warning("Spotify set_volume falhou: %s", exc)

    def get_current_track(self) -> Optional[str]:
        sp = self._get_client()
        if sp is None:
            logger.warning("Spotify indisponível.")
            return None
        try:
            current = sp.current_playback()
            if current and current.get("item"):
                item = current["item"]
                artists = ", ".join(a["name"] for a in item.get("artists", []))
                name = item.get("name", "")
                return f"{name} — {artists}" if artists else name
            return None
        except Exception as exc:
            logger.warning("Spotify get_current_track falhou: %s", exc)
            return None

    def handle_voice_command(self, text: str) -> Optional[str]:
        text_lower = text.lower().strip()

        if re.match(r"^toca\b", text_lower):
            query = re.sub(r"^toca\s*", "", text_lower).strip()
            self.play(query if query else None)
            return f"Tocando {query}." if query else "Retomando reprodução."

        if any(p in text_lower for p in ("pausa", "parar música", "pausar")):
            self.pause()
            return "Música pausada."

        if any(p in text_lower for p in ("próxima", "proxima", "pula", "pular")):
            self.next_track()
            return "Próxima música."

        if any(p in text_lower for p in ("anterior", "volta", "voltar")):
            self.previous_track()
            return "Música anterior."

        match = re.search(r"volume\s+(\d+)", text_lower)
        if match:
            vol = int(match.group(1))
            self.set_volume(vol)
            return f"Volume ajustado para {vol}%."

        if any(p in text_lower for p in ("que música é essa", "o que está tocando", "qual música")):
            track = self.get_current_track()
            return f"Tocando: {track}." if track else "Nenhuma música tocando no momento."

        return None
