"""Tests for the file-based credential store (~/.yumii/auth.json).

These tests never touch the real user files or the legacy OS keychain —
they redirect the module-level paths into a temp directory and disable
the one-time keyring migration.
"""

import json
from pathlib import Path

import pytest

from yumii.core import credential_store as cs


@pytest.fixture
def isolated_auth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the store to a temp auth.json and skip keyring migration."""
    auth_file = tmp_path / "auth.json"
    monkeypatch.setattr(cs, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cs, "AUTH_FILE", auth_file)
    monkeypatch.setattr(cs, "_migration_attempted", True)
    return auth_file


# ---------------------------------------------------------------------------
# Key classification (unchanged contract)
# ---------------------------------------------------------------------------


def test_credential_keys_are_secrets_only():
    """A key in both sets would race the auth write against the config write."""
    overlap = cs.CREDENTIAL_KEYS & cs.PREFERENCE_KEYS
    assert overlap == set(), f"Secret keys leaking into preferences: {overlap}"


def test_credential_keys_contains_all_providers():
    expected = {
        "ELEVENLABS_API_KEY",
        "ELEVENLABS_VOICE_ID",
        "CAMB_API_KEY",
        "CAMB_VOICE_ID",
        "GROQ_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    }
    assert expected.issubset(cs.CREDENTIAL_KEYS)


def test_preference_keys_have_no_secrets():
    assert "LLM_PROVIDER" in cs.PREFERENCE_KEYS
    assert "PERSONALITY" in cs.PREFERENCE_KEYS
    assert "GROQ_API_KEY" not in cs.PREFERENCE_KEYS
    assert "ELEVENLABS_API_KEY" not in cs.PREFERENCE_KEYS


# ---------------------------------------------------------------------------
# File round-trips
# ---------------------------------------------------------------------------


def test_get_returns_none_when_file_missing(isolated_auth: Path):
    assert cs.get_credential("GROQ_API_KEY") is None
    assert not cs.is_set("GROQ_API_KEY")


def test_save_get_delete_round_trip(isolated_auth: Path):
    cs.save_credential("GROQ_API_KEY", "gsk_test123")
    assert cs.get_credential("GROQ_API_KEY") == "gsk_test123"
    assert cs.is_set("GROQ_API_KEY")

    cs.delete_credential("GROQ_API_KEY")
    assert cs.get_credential("GROQ_API_KEY") is None


def test_save_merges_instead_of_overwriting(isolated_auth: Path):
    cs.save_credential("GROQ_API_KEY", "gsk_a")
    cs.save_credential("CAMB_API_KEY", "camb_b")
    raw = json.loads(isolated_auth.read_text(encoding="utf-8"))
    assert raw == {"GROQ_API_KEY": "gsk_a", "CAMB_API_KEY": "camb_b"}


def test_load_all_filters_unknown_keys(isolated_auth: Path):
    """A hand-edited auth.json must not inject arbitrary env vars."""
    isolated_auth.write_text(
        json.dumps({"GROQ_API_KEY": "gsk_x", "PATH": "evil", "EMPTY": ""}),
        encoding="utf-8",
    )
    assert cs.load_all() == {"GROQ_API_KEY": "gsk_x"}


def test_corrupt_auth_file_is_set_aside_not_clobbered(isolated_auth: Path):
    isolated_auth.write_text("{ not valid json", encoding="utf-8")
    assert cs.get_credential("GROQ_API_KEY") is None
    # the corrupt content must be preserved for manual recovery
    corrupt = isolated_auth.with_suffix(".json.corrupt")
    assert corrupt.exists()
    assert "not valid json" in corrupt.read_text(encoding="utf-8")


def test_no_tmp_file_left_behind(isolated_auth: Path):
    cs.save_credential("GROQ_API_KEY", "gsk_a")
    assert not isolated_auth.with_suffix(".json.tmp").exists()


# ---------------------------------------------------------------------------
# Plaintext config.json migration
# ---------------------------------------------------------------------------


def test_migrate_from_plaintext_moves_secrets(isolated_auth: Path):
    config = {
        "LLM_PROVIDER": "Groq",
        "GROQ_API_KEY": "gsk_leaked",
        "PERSONALITY": "caring",
    }
    cleaned = cs.migrate_from_plaintext(config)
    assert cleaned == {"LLM_PROVIDER": "Groq", "PERSONALITY": "caring"}
    assert cs.get_credential("GROQ_API_KEY") == "gsk_leaked"


def test_migrate_from_plaintext_does_not_overwrite_existing(isolated_auth: Path):
    cs.save_credential("GROQ_API_KEY", "gsk_current")
    cleaned = cs.migrate_from_plaintext({"GROQ_API_KEY": "gsk_stale"})
    assert cleaned == {}
    # auth.json wins; the stale plaintext copy is discarded
    assert cs.get_credential("GROQ_API_KEY") == "gsk_current"
