"""File-based secret storage at ~/.yumii/auth.json (owner-only, atomic writes).

Secrets live here, never in config.json. A legacy OS-keychain store from
installs before 0.6 is migrated in automatically on first read.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".yumii"
AUTH_FILE = CONFIG_DIR / "auth.json"

# Legacy keychain identifier — only needed for migration.
SERVICE_NAME = "Yumii"

# Secrets — live ONLY in auth.json.
CREDENTIAL_KEYS: frozenset[str] = frozenset(
    {
        "ELEVENLABS_API_KEY",
        "ELEVENLABS_VOICE_ID",
        "CAMB_API_KEY",
        "CAMB_VOICE_ID",
        "GROQ_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "OLLAMA_API_KEY",
        "COMPOSIO_API_KEY",
    }
)

# Preferences — safe in plaintext config.json.
PREFERENCE_KEYS: frozenset[str] = frozenset(
    {
        "LLM_PROVIDER",
        "GROQ_MODEL",
        "OLLAMA_MODEL",
        "OLLAMA_BASE_URL",
        "PERSONALITY",
        "TTS_PROVIDER",
        "STT_PROVIDER",
        "WHISPER_MODEL_SIZE",
        "VOSK_MODEL_SIZE",
        "KOKORO_VOICE",
        "KOKORO_MODEL_SIZE",
        "HITL_MODE",
        "COMPUTE_PROFILE",
    }
)

# Probe the legacy keychain at most once per process.
_migration_attempted = False


# ---------------------------------------------------------------------------
# File primitives
# ---------------------------------------------------------------------------


def _write_auth(data: dict[str, str]) -> None:
    """Atomically write *data* to auth.json with owner-only permissions."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = AUTH_FILE.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp, AUTH_FILE)
    try:
        # 0600 — owner only (advisory on Windows; real on macOS/Linux).
        os.chmod(AUTH_FILE, 0o600)
    except OSError:
        pass


def _read_auth() -> dict[str, str]:
    """Read auth.json, migrating from the legacy keychain on first run."""
    _migrate_from_keyring_once()
    try:
        with AUTH_FILE.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        # Set a corrupt file aside instead of clobbering it on the next save.
        corrupt = AUTH_FILE.with_suffix(".json.corrupt")
        log.warning("auth.json is not valid JSON; moving it to %s", corrupt)
        try:
            os.replace(AUTH_FILE, corrupt)
        except OSError:
            pass
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if isinstance(v, str) and v}


def _migrate_from_keyring_once() -> None:
    """Copy legacy OS-keychain secrets into auth.json, once per process (never raises)."""
    global _migration_attempted
    if _migration_attempted:
        return
    _migration_attempted = True
    if AUTH_FILE.exists():
        return
    try:
        import keyring  # noqa: PLC0415 — optional legacy dependency
    except ImportError:
        return
    found: dict[str, str] = {}
    for key in CREDENTIAL_KEYS:
        try:
            value = keyring.get_password(SERVICE_NAME, key)
        except Exception:
            return
        if value:
            found[key] = value
    if found:
        _write_auth(found)
        log.info("migrated %d credentials from the OS keychain to %s", len(found), AUTH_FILE)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def save_credential(key: str, value: str) -> None:
    """Save a secret to auth.json."""
    data = _read_auth()
    data[key] = value
    _write_auth(data)


def get_credential(key: str) -> Optional[str]:
    """Read a secret from auth.json. Returns None if not found."""
    return _read_auth().get(key)


def delete_credential(key: str) -> None:
    """Remove a secret from auth.json."""
    data = _read_auth()
    if key in data:
        del data[key]
        _write_auth(data)


def is_set(key: str) -> bool:
    """Return True if the credential exists in auth.json."""
    return get_credential(key) is not None


def load_all() -> dict[str, str]:
    """Return stored credentials, filtered to CREDENTIAL_KEYS (no arbitrary env injection)."""
    return {k: v for k, v in _read_auth().items() if k in CREDENTIAL_KEYS}


def migrate_from_plaintext(config: dict) -> dict:
    """Move any credential keys out of plaintext config.json into auth.json."""
    cleaned: dict[str, str] = {}
    auth = _read_auth()
    changed = False
    for key, value in config.items():
        if key in CREDENTIAL_KEYS and value:
            if key not in auth:
                auth[key] = str(value)
                changed = True
        else:
            cleaned[key] = value
    if changed:
        _write_auth(auth)
    return cleaned
