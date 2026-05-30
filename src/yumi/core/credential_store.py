"""
Credential store — secure secret storage using the OS keychain.

Platform backends (handled automatically by the `keyring` library):
  Windows : Windows Credential Manager  (Control Panel → Credential Manager)
  macOS   : macOS Keychain
  Linux   : libsecret (GNOME Keyring) or KWallet

API keys are NEVER written to disk as plaintext.
Non-sensitive preferences (personality, provider choice) stay in config.json.
"""
from __future__ import annotations

import sys
from typing import Optional

import keyring
import keyring.errors

# Service name used as the "application" identifier in the OS keychain
SERVICE_NAME = "Yumi"

# Keys that are secrets (live ONLY in the OS keychain)
CREDENTIAL_KEYS: frozenset[str] = frozenset({
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_VOICE_ID",
    "CAMB_API_KEY",
    "CAMB_VOICE_ID",
    "GROQ_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
})

# Keys that are preferences (safe to store in plaintext config.json)
PREFERENCE_KEYS: frozenset[str] = frozenset({
    "LLM_PROVIDER",
    "PERSONALITY",
    "TTS_PROVIDER",
    "STT_PROVIDER",
    "WHISPER_MODEL_SIZE",
    "COMPUTE_PROFILE",
})


def keychain_name() -> str:
    """Human-readable name of the OS keychain backend."""
    if sys.platform == "win32":
        return "Windows Credential Manager"
    elif sys.platform == "darwin":
        return "macOS Keychain"
    else:
        return "OS Keychain (libsecret)"


def save_credential(key: str, value: str) -> None:
    """Save a secret to the OS keychain."""
    keyring.set_password(SERVICE_NAME, key, value)


def get_credential(key: str) -> Optional[str]:
    """Read a secret from the OS keychain. Returns None if not found."""
    try:
        return keyring.get_password(SERVICE_NAME, key)
    except Exception:
        return None


def delete_credential(key: str) -> None:
    """Remove a secret from the OS keychain."""
    try:
        keyring.delete_password(SERVICE_NAME, key)
    except (keyring.errors.PasswordDeleteError, Exception):
        pass


def is_set(key: str) -> bool:
    """Return True if the credential exists in the keychain."""
    return get_credential(key) is not None


def load_all() -> dict[str, str]:
    """Return every stored Yumi credential as a plain dict."""
    result: dict[str, str] = {}
    for key in CREDENTIAL_KEYS:
        value = get_credential(key)
        if value is not None:
            result[key] = value
    return result


def migrate_from_plaintext(config: dict) -> dict:
    """
    One-time migration: any credential key found in the plaintext config.json
    is moved into the OS keychain and removed from the returned dict.

    Safe to call on every startup — it is a no-op when migration is already done.
    Returns the cleaned config dict containing preferences only.
    """
    cleaned: dict[str, str] = {}
    for key, value in config.items():
        if key in CREDENTIAL_KEYS and value:
            # Only write to keychain if not already stored there
            if get_credential(key) is None:
                save_credential(key, value)
            # Strip from plaintext regardless
        else:
            cleaned[key] = value
    return cleaned
