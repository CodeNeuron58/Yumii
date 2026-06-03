"""Tests for the global (non-sensitive) config file.

These tests never write to the real user config — they work in a
temp directory by monkey-patching the module-level constants.
"""

import json
from pathlib import Path

import pytest

from yumi.core import global_config


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect the config module to a temporary file for the test."""
    test_file = tmp_path / "config.json"
    monkeypatch.setattr(global_config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(global_config, "CONFIG_FILE", test_file)
    return test_file


def test_load_returns_empty_dict_when_file_missing(isolated_config: Path) -> None:
    """A first run (no config file yet) should return an empty dict, not raise."""
    assert global_config.load_global_config() == {}


def test_update_then_load_round_trips(isolated_config: Path) -> None:
    """An update followed by a load should return the same value."""
    global_config.update_global_config("LLM_PROVIDER", "Groq")
    assert global_config.load_global_config() == {"LLM_PROVIDER": "Groq"}


def test_multiple_updates_merge(isolated_config: Path) -> None:
    """Successive updates should accumulate keys, not overwrite the file each time."""
    global_config.update_global_config("LLM_PROVIDER", "OpenAI")
    global_config.update_global_config("PERSONALITY", "tsundere")
    cfg = global_config.load_global_config()
    assert cfg["LLM_PROVIDER"] == "OpenAI"
    assert cfg["PERSONALITY"] == "tsundere"


def test_save_persists_to_disk(isolated_config: Path) -> None:
    """A save followed by a fresh process load should read the same data."""
    global_config.update_global_config("PERSONALITY", "yandere")
    # Reload from disk as if a new process started
    raw = json.loads(isolated_config.read_text(encoding="utf-8"))
    assert raw["PERSONALITY"] == "yandere"


def test_corrupted_config_returns_empty_dict(isolated_config: Path) -> None:
    """A malformed JSON file should not crash the load function."""
    isolated_config.write_text("{ not valid json", encoding="utf-8")
    assert global_config.load_global_config() == {}
