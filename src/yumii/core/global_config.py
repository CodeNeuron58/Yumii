"""Non-sensitive preferences file at ~/.yumii/config.json (secrets: see credential_store)."""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".yumii"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_global_config() -> dict:
    """Load preferences from config.json (migrating any stale secrets to auth.json)."""
    if not CONFIG_FILE.exists():
        return {}

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            raw: dict = json.load(f)
    except json.JSONDecodeError:
        return {}

    from yumii.core.credential_store import CREDENTIAL_KEYS, migrate_from_plaintext

    if any(k in CREDENTIAL_KEYS for k in raw):
        cleaned = migrate_from_plaintext(raw)
        save_global_config(cleaned)
        return cleaned

    return raw


def save_global_config(config_data: dict) -> None:
    """Persist preferences to config.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4)


def update_global_config(key: str, value: str) -> None:
    """Update a single preference key."""
    config = load_global_config()
    config[key] = value
    save_global_config(config)
