"""Credential store — file-based secret storage (``~/.yumii/auth.json``).

API keys live in a JSON file created with owner-only permissions, the
same model tools like Claude Code and opencode use:

    ~/.yumii/config.json   # non-sensitive preferences (see global_config.py)
    ~/.yumii/auth.json     # secrets, e.g. {"GROQ_API_KEY": "gsk_..."}

Writes are atomic (temp file + rename) so a crash mid-save can't
truncate the file. A corrupt auth.json is set aside as
``auth.json.corrupt`` rather than silently overwritten.

Migration: installs prior to 0.6 stored secrets in the OS keychain via
the ``keyring`` library. If ``auth.json`` doesn't exist yet and keyring
is importable, those entries are copied over automatically on first
read. The keychain entries themselves are left untouched — remove them
manually (Windows: Control Panel → Credential Manager → Windows
Credentials → entries named "Yumii:<KEY>").
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

# Service name older versions used as the keychain identifier; still
# needed to find legacy entries during migration.
SERVICE_NAME = "Yumii"

# Keys that are secrets (live ONLY in auth.json)
CREDENTIAL_KEYS: frozenset[str] = frozenset(
    {
        "ELEVENLABS_API_KEY",
        "ELEVENLABS_VOICE_ID",
        "CAMB_API_KEY",
        "CAMB_VOICE_ID",
        "GROQ_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "COMPOSIO_API_KEY",
    }
)

# Keys that are preferences (safe to store in plaintext config.json)
PREFERENCE_KEYS: frozenset[str] = frozenset(
    {
        "LLM_PROVIDER",
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

# One attempt per process; flipped to True after the first check so a
# missing auth.json doesn't re-probe the keychain on every read.
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
        # Owner read/write only. On Windows this is mostly advisory —
        # the user-profile ACLs are the real gate — but it matters on
        # macOS/Linux.
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
        # Don't let a corrupt file get silently clobbered by the next
        # save — set it aside so the keys inside remain recoverable.
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
    """Copy legacy OS-keychain entries into auth.json, once per process.

    Only runs when auth.json doesn't exist and the (no longer required)
    ``keyring`` package happens to be importable. Never raises.
    """
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
# Public API (unchanged signatures)
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
    """Return every stored Yumii credential as a plain dict.

    Filtered to :data:`CREDENTIAL_KEYS` so a hand-edited auth.json can't
    inject arbitrary environment variables at startup.
    """
    return {k: v for k, v in _read_auth().items() if k in CREDENTIAL_KEYS}


def migrate_from_plaintext(config: dict) -> dict:
    """One-time migration of credentials out of config.json.

    Any credential key found in the plaintext config.json is moved into
    auth.json and removed from the returned dict.
    """
    cleaned: dict[str, str] = {}
    auth = _read_auth()
    changed = False
    for key, value in config.items():
        if key in CREDENTIAL_KEYS and value:
            if key not in auth:
                auth[key] = str(value)
                changed = True
            # Strip from plaintext config regardless
        else:
            cleaned[key] = value
    if changed:
        _write_auth(auth)
    return cleaned
