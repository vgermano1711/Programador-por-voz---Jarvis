import re
import unicodedata


_DEFAULT_MODELS: dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-8",
}

_OPUS_PATTERNS: list[str] = [
    r"analise profundamente",
    r"revis[aã]o completa",
    r"arquitetura",
    r"refatore tudo",
    r"explique detalhadamente",
]

_SONNET_PATTERNS: list[str] = [
    r"\bexplique\b",
    r"\bcompare\b",
    r"como funciona",
    r"\bpor que\b",
    r"diferen[cç]a",
]

_OPUS_RE = re.compile("|".join(_OPUS_PATTERNS), re.IGNORECASE)
_SONNET_RE = re.compile("|".join(_SONNET_PATTERNS), re.IGNORECASE)


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


class ModelRouter:
    def __init__(self, config: dict | None = None) -> None:
        cfg = config or {}
        self._models: dict[str, str] = {
            "haiku": cfg.get("haiku_model", _DEFAULT_MODELS["haiku"]),
            "sonnet": cfg.get("sonnet_model", _DEFAULT_MODELS["sonnet"]),
            "opus": cfg.get("opus_model", _DEFAULT_MODELS["opus"]),
        }

    def _select_tier(self, text: str) -> str:
        normalized = _normalize(text)
        if len(text) > 500 or _OPUS_RE.search(normalized):
            return "opus"
        if 100 <= len(text) <= 500 or _SONNET_RE.search(normalized):
            return "sonnet"
        return "haiku"

    def route(self, text: str) -> tuple[str, str]:
        tier = self._select_tier(text)
        return self._models[tier], tier

    def explain(self, text: str) -> str:
        tier = self._select_tier(text)
        model_id = self._models[tier]
        reasons: list[str] = []

        if tier == "opus":
            if len(text) > 500:
                reasons.append(f"texto longo ({len(text)} chars > 500)")
            match = _OPUS_RE.search(_normalize(text))
            if match:
                reasons.append(f"padrão opus detectado: '{match.group()}'")
        elif tier == "sonnet":
            if 100 <= len(text) <= 500:
                reasons.append(f"comprimento médio ({len(text)} chars, 100–500)")
            match = _SONNET_RE.search(_normalize(text))
            if match:
                reasons.append(f"padrão sonnet detectado: '{match.group()}'")
        else:
            reasons.append(f"texto curto ({len(text)} chars) sem padrões especiais")

        reason_str = "; ".join(reasons) if reasons else "sem padrões específicos"
        return f"Roteado para {tier.upper()} ({model_id}): {reason_str}"
