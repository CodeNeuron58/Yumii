import json
from pathlib import Path

# Use pathlib to point to ~/.yumi/config.json
# This works identically on Windows (C:\Users\Name\.yumi) and Linux/Mac (/home/name/.yumi)
CONFIG_DIR = Path.home() / ".yumi"
CONFIG_FILE = CONFIG_DIR / "config.json"

def load_global_config() -> dict:
    """Loads the config from the user's global home directory (~/.yumi/config.json)."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_global_config(config_data: dict):
    """Saves the config to the user's global home directory."""
    # Ensure the ~/.yumi directory exists
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4)

def update_global_config(key: str, value: str):
    """Updates a single key in the global config."""
    config = load_global_config()
    config[key] = value
    save_global_config(config)
