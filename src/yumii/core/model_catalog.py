"""Model catalog: a models.dev snapshot + Yumii's own provider wiring.

The OpenCode pattern, in Python: model choices come from DATA, never free
text. The snapshot (a filtered models.dev ``api.json`` — MIT) lists every
chat model for the providers Yumii can actually wire; this module layers
Yumii's side on top: which LangChain client builds each provider, which
auth.json key it needs, and which base URL speaks for it.

Refresh: ``refresh_catalog()`` re-fetches models.dev and writes a user copy
to ``~/.yumii/model-catalog.json`` (loaded in preference to the bundled
asset). Network failures are non-fatal — the bundled snapshot always works.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

_BUNDLED_ASSET = Path(__file__).resolve().parent.parent / "assets" / "model_catalog.json"
_USER_FILE = Path.home() / ".yumii" / "model-catalog.json"
_API_URL = "https://models.dev/api.json"


@dataclass(frozen=True)
class ProviderWiring:
    """How Yumii talks to a provider (the part models.dev can't tell us)."""

    id: str
    name: str
    kind: str  # "anthropic" | "groq" | "ollama" | "openai" | "openai-compatible"
    env_key: str  # auth.json / env var name for the API key
    base_url: str | None = None  # openai-compatible endpoints
    key_optional: bool = False  # local Ollama needs no key


# Base URLs are Yumii's own constants — models.dev lists SDK packages, not
# endpoints. These are the providers' documented OpenAI-compatible surfaces.
PROVIDER_WIRING: dict[str, ProviderWiring] = {
    "anthropic": ProviderWiring("anthropic", "Anthropic", "anthropic", "ANTHROPIC_API_KEY"),
    "openai": ProviderWiring("openai", "OpenAI", "openai", "OPENAI_API_KEY"),
    "groq": ProviderWiring("groq", "Groq", "groq", "GROQ_API_KEY"),
    "opencode": ProviderWiring("opencode", "OpenCode Zen", "openai-compatible", "OPENCODE_API_KEY",
                               base_url="https://opencode.ai/zen/v1"),
    "ollama": ProviderWiring("ollama", "Ollama (local / cloud)", "ollama", "OLLAMA_API_KEY", key_optional=True),
    "google": ProviderWiring(
        "google", "Google Gemini", "openai-compatible", "GEMINI_API_KEY",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
    ),
    "openrouter": ProviderWiring("openrouter", "OpenRouter", "openai-compatible", "OPENROUTER_API_KEY",
                                 base_url="https://openrouter.ai/api/v1"),
    "deepseek": ProviderWiring("deepseek", "DeepSeek", "openai-compatible", "DEEPSEEK_API_KEY",
                               base_url="https://api.deepseek.com/v1"),
    "xai": ProviderWiring("xai", "xAI (Grok)", "openai-compatible", "XAI_API_KEY",
                          base_url="https://api.x.ai/v1"),
    "togetherai": ProviderWiring("togetherai", "Together AI", "openai-compatible", "TOGETHER_API_KEY",
                                 base_url="https://api.together.xyz/v1"),
    "mistral": ProviderWiring("mistral", "Mistral", "openai-compatible", "MISTRAL_API_KEY",
                              base_url="https://api.mistral.ai/v1"),
}

# legacy aliases users may have typed in config.json
_PROVIDER_ALIASES = {"together": "togetherai", "x.ai": "xai", "grok": "xai"}


def canonical_provider(provider: str) -> str | None:
    """Map a configured provider string to a wiring id (case-insensitive)."""
    p = (provider or "").strip().lower()
    p = _PROVIDER_ALIASES.get(p, p)
    return p if p in PROVIDER_WIRING else None


# ---------------------------------------------------------------------------
# Snapshot loading
# ---------------------------------------------------------------------------

_cache: dict | None = None


def _load_snapshot(user_file: Path | None = None) -> dict:
    path = user_file or _USER_FILE
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))["providers"]
        except Exception:
            log.warning("model_catalog_user_file_broken", extra={"path": str(path)})
    if _BUNDLED_ASSET.exists():
        return json.loads(_BUNDLED_ASSET.read_text(encoding="utf-8"))["providers"]
    return {}


def _get(user_file: Path | None = None) -> dict:
    global _cache
    if _cache is None:
        _cache = _load_snapshot(user_file)
    return _cache


def reload_catalog() -> None:
    """Drop the cache (after a refresh, or in tests)."""
    global _cache
    _cache = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def providers() -> list[dict]:
    """Provider entries for the picker: wiring + snapshot presence."""
    snapshot = _get()
    out = []
    for pid, wiring in PROVIDER_WIRING.items():
        models = snapshot.get(pid, {}).get("models", {})
        out.append(
            {
                "id": wiring.id,
                "name": wiring.name,
                "env_key": wiring.env_key,
                "doc": snapshot.get(pid, {}).get("doc"),
                "key_optional": wiring.key_optional,
                "model_count": len(models) if pid != "ollama" else None,
                "connected": bool(os.environ.get(wiring.env_key)) or wiring.key_optional,
            }
        )
    return out


def get_wiring(provider: str) -> ProviderWiring | None:
    return PROVIDER_WIRING.get(canonical_provider(provider) or "")


def _slim(mid: str, m: dict) -> dict:
    limit = m.get("limit") or {}
    cost = m.get("cost") or {}
    return {
        "id": m.get("id", mid),
        "name": m.get("name", mid),
        "tool_call": bool(m.get("tool_call")),
        "reasoning": bool(m.get("reasoning")),
        "context": limit.get("context"),
        "max_output": limit.get("output"),
        "cost_in": cost.get("input"),
        "cost_out": cost.get("output"),
    }


def models(provider: str) -> list[dict]:
    """Chat models for a provider from the snapshot (Ollama is handled separately)."""
    pid = canonical_provider(provider)
    if not pid:
        return []
    return [
        _slim(mid, m)
        for mid, m in (_get().get(pid, {}).get("models", {})).items()
    ]


def get_model(provider: str, model_id: str) -> dict | None:
    pid = canonical_provider(provider)
    if not pid:
        return None
    m = _get().get(pid, {}).get("models", {}).get(model_id)
    return _slim(model_id, m) if m else None


def key_for(provider: str) -> str | None:
    """The provider's API key from env (auth.json is loaded into env at boot)."""
    wiring = get_wiring(provider)
    if wiring is None:
        return None
    return os.environ.get(wiring.env_key)


def _parse_ollama_tags(data: dict) -> list[dict]:
    out = []
    for m in data.get("models", []):
        name = m.get("name") or m.get("model") or ""
        if name:
            out.append({"id": name, "name": name, "tool_call": None, "reasoning": None,
                        "context": None, "max_output": None, "cost_in": None, "cost_out": None})
    return out


async def ollama_local_models(base_url: str, api_key: str | None) -> list[dict]:
    """Models installed on the (local or cloud) Ollama server — the live catalog."""
    import aiohttp

    url = f"{base_url.rstrip('/')}/api/tags"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as s:
            async with s.get(url) as resp:
                resp.raise_for_status()
                data = await resp.json()
    except Exception as e:
        log.warning("ollama_tags_unreachable", extra={"error": str(e)})
        return []
    return _parse_ollama_tags(data)


# ---------------------------------------------------------------------------
# Refresh (rebuild the user snapshot from models.dev)
# ---------------------------------------------------------------------------


def _fetch_and_filter(url: str, timeout: float) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "yumii"})
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        full = json.load(resp)

    def keep(m: dict) -> bool:
        mod = m.get("modalities") or {}
        return "text" in (mod.get("input") or []) and "text" in (mod.get("output") or [])

    out = {}
    for pid, wiring in PROVIDER_WIRING.items():
        if pid == "ollama":
            continue  # live from /api/tags, not from models.dev
        src = full.get(pid) or {}
        out[pid] = {
            "id": pid,
            "name": wiring.name,
            "env": [wiring.env_key],
            "doc": src.get("doc"),
            "models": {mid: m for mid, m in (src.get("models") or {}).items() if keep(m)},
        }
    return out


def refresh_catalog(
    target: Path | None = None,
    source_url: str | None = None,
    timeout: float = 30.0,
) -> int:
    """Re-fetch models.dev and write a user snapshot. Returns total model count."""
    filtered = _fetch_and_filter(source_url or _API_URL, timeout)
    path = target or _USER_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps({"source": _API_URL, "providers": filtered}, separators=(",", ":")),
        encoding="utf-8",
    )
    os.replace(str(tmp), str(path))
    reload_catalog()
    total = sum(len(p["models"]) for p in filtered.values())
    log.info("model_catalog_refreshed", extra={"models": total, "path": str(path)})
    return total


__all__ = [
    "PROVIDER_WIRING",
    "ProviderWiring",
    "canonical_provider",
    "get_wiring",
    "providers",
    "models",
    "get_model",
    "key_for",
    "ollama_local_models",
    "refresh_catalog",
    "reload_catalog",
]
