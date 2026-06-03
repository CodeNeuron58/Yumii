"""Manages the non-sensitive JSON preference file located at ~/.yumii/config.json."""

import json
from pathlib import Path

# ~/.yumii/config.json stores ONLY non-sensitive preferences.
# Secrets (API keys) live in the OS keychain — see credential_store.py.
CONFIG_DIR = Path.home() / ".yumii"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_global_config() -> dict:
    """Load preferences from ~/.yumii/config.json.

    On first load after an upgrade, any credential keys still present in the
    file are automatically migrated to the OS keychain and removed from disk.
    """
    if not CONFIG_FILE.exists():
        return {}

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            raw: dict = json.load(f)
    except json.JSONDecodeError:
        return {}

    # Auto-migrate stale plaintext credentials to the OS keychain
    from yumii.core.credential_store import CREDENTIAL_KEYS, migrate_from_plaintext

    if any(k in CREDENTIAL_KEYS for k in raw):
        cleaned = migrate_from_plaintext(raw)
        save_global_config(cleaned)
        return cleaned

    return raw


def save_global_config(config_data: dict) -> None:
    """Persist preferences to ~/.yumii/config.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4)


def update_global_config(key: str, value: str) -> None:
    """Update a single preference key in the global config."""
    config = load_global_config()
    config[key] = value
    save_global_config(config)
