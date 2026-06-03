"""Tests for the OS-keychain credential store.

These tests do not actually call the OS keychain. They exercise the
in-memory logic, key-validation lists, and credential-name conventions.
"""

from yumi.core.credential_store import (
    CREDENTIAL_KEYS,
    PREFERENCE_KEYS,
    SERVICE_NAME,
    keychain_name,
)


def test_service_name_is_yumi():
    """The keychain service identifier must be exactly 'Yumi'."""
    assert SERVICE_NAME == "Yumi"


def test_credential_keys_are_secrets_only():
    """All keys in CREDENTIAL_KEYS must NOT be in PREFERENCE_KEYS.

    If a key appears in both, the migration logic in global_config.py
    would race the keychain write against the disk write.
    """
    overlap = CREDENTIAL_KEYS & PREFERENCE_KEYS
    assert overlap == set(), f"Secret keys leaking into preferences: {overlap}"


def test_credential_keys_contains_all_providers():
    """Each advertised LLM/TTS provider must have a credential entry."""
    expected = {
        "ELEVENLABS_API_KEY",
        "ELEVENLABS_VOICE_ID",
        "CAMB_API_KEY",
        "CAMB_VOICE_ID",
        "GROQ_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    }
    assert expected.issubset(CREDENTIAL_KEYS)


def test_preference_keys_have_no_secrets():
    """Preferences must only include non-sensitive values."""
    assert "LLM_PROVIDER" in PREFERENCE_KEYS
    assert "PERSONALITY" in PREFERENCE_KEYS
    assert "STT_PROVIDER" in PREFERENCE_KEYS
    assert "WHISPER_MODEL_SIZE" in PREFERENCE_KEYS
    # API keys must NEVER be in preferences
    assert "GROQ_API_KEY" not in PREFERENCE_KEYS
    assert "ELEVENLABS_API_KEY" not in PREFERENCE_KEYS


def test_keychain_name_is_platform_aware():
    """The user-facing name of the keychain must be a non-empty string."""
    name = keychain_name()
    assert isinstance(name, str)
    assert len(name) > 0
