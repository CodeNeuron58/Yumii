"""Smoke tests for the REST surface: /health, /api/status, settings, and the model picker.

The engine is never initialized here — TestClient without a lifespan context
skips engine boot entirely. Config/auth files are redirected into a temp dir
and anything the API writes into os.environ or the settings singleton is
restored afterwards, so the real user files are never touched.

These exist because the provider→key mapping and the settings write path
shipped regressions with zero endpoint coverage (the 2026-09 audit).
"""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from yumii.api import server
from yumii.core import credential_store as cs
from yumii.core import global_config as gc
from yumii.core import model_catalog as mc
from yumii.core.config import settings

# Every env var the API may write (provider selection + credential mirroring),
# snapshotted and restored around each test.
_TRACKED_ENV = set(cs.CREDENTIAL_KEYS) | {"LLM_PROVIDER", "LLM_MODEL"}

# Settings fields the API mirrors credentials into (server._CREDENTIAL_SETTINGS_FIELDS).
_MIRRORED_FIELDS = sorted(set(server._CREDENTIAL_SETTINGS_FIELDS.values()))


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """App test client with config/auth redirected to temp files."""
    monkeypatch.setattr(gc, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(gc, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(cs, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cs, "AUTH_FILE", tmp_path / "auth.json")
    monkeypatch.setattr(cs, "_migration_attempted", True)

    # Clean baseline for everything the API mutates; monkeypatch restores
    # the originals at teardown even if the API rewrites them mid-test.
    for key in _TRACKED_ENV:
        monkeypatch.delenv(key, raising=False)
    for field in _MIRRORED_FIELDS:
        monkeypatch.setattr(settings, field, None)
    monkeypatch.setattr(settings, "llm_provider", "Ollama")
    monkeypatch.setattr(settings, "llm_model", None)

    # No `with` → the lifespan (engine.initialize) never runs.
    yield TestClient(server.app)

    # os.environ writes done by app code aren't tracked by monkeypatch —
    # restore exactly what was there before the test.
    for key in _TRACKED_ENV:
        os.environ.pop(key, None)


# ---------------------------------------------------------------------------
# /health + /api/status — the provider → key-name mapping
# ---------------------------------------------------------------------------


def test_health_ok(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_status_google_configured_with_gemini_key(client: TestClient) -> None:
    """Google keys live under GEMINI_API_KEY — provider.upper() built
    GOOGLE_API_KEY and reported every Google user unconfigured forever."""
    gc.update_global_config("LLM_PROVIDER", "google")

    body = client.get("/api/status").json()
    assert body["provider"] == "google"
    assert body["configured"] is False  # no key yet

    cs.save_credential("GEMINI_API_KEY", "test-key-123")
    body = client.get("/api/status").json()
    assert body["configured"] is True


def test_status_togetherai_maps_to_together_key(client: TestClient) -> None:
    gc.update_global_config("LLM_PROVIDER", "togetherai")
    cs.save_credential("TOGETHER_API_KEY", "test-key-123")
    assert client.get("/api/status").json()["configured"] is True


def test_status_key_optional_provider_needs_no_key(client: TestClient) -> None:
    """A local Ollama user has no key — they must still pass first-run."""
    gc.update_global_config("LLM_PROVIDER", "ollama")
    assert client.get("/api/status").json()["configured"] is True


def test_status_legacy_capitalized_provider_canonicalizes(client: TestClient) -> None:
    gc.update_global_config("LLM_PROVIDER", "Ollama")
    body = client.get("/api/status").json()
    assert body["configured"] is True  # key_optional via canonical 'ollama'


def test_status_unknown_provider_reports_unconfigured(client: TestClient) -> None:
    gc.update_global_config("LLM_PROVIDER", "nonsense-ai")
    assert client.get("/api/status").json()["configured"] is False


# ---------------------------------------------------------------------------
# /api/settings — choices, defaults, and the write path
# ---------------------------------------------------------------------------


def test_settings_choices_include_catalog_providers(client: TestClient) -> None:
    choices = client.get("/api/settings").json()["choices"]["LLM_PROVIDER"]
    assert "google" in choices
    assert "openrouter" in choices
    assert "togetherai" in choices


def test_settings_reports_real_default_provider(client: TestClient) -> None:
    """A fresh install runs Ollama — the old code reported choices[0] ('Groq')."""
    body = client.get("/api/settings").json()
    assert body["preferences"]["LLM_PROVIDER"] == "Ollama"
    assert body["choices"]["LLM_PROVIDER"][0] != "Ollama"  # the default isn't a coincidence


def test_put_settings_accepts_lowercase_catalog_provider(client: TestClient) -> None:
    """The picker writes 'google' — the old whitelist 400'd it, so any other
    settings save made through a stale UI silently flipped the provider."""
    r = client.put("/api/settings", json={"preferences": {"LLM_PROVIDER": "google"}})
    assert r.status_code == 200
    assert gc.load_global_config()["LLM_PROVIDER"] == "google"
    assert os.environ["LLM_PROVIDER"] == "google"
    assert settings.llm_provider == "google"


def test_put_settings_canonicalizes_legacy_capitalization(client: TestClient) -> None:
    """The orb's onboarding PUTs 'Ollama' — it must keep working."""
    r = client.put("/api/settings", json={"preferences": {"LLM_PROVIDER": "Ollama"}})
    assert r.status_code == 200
    assert gc.load_global_config()["LLM_PROVIDER"] == "ollama"


def test_put_settings_rejects_unknown_provider(client: TestClient) -> None:
    r = client.put("/api/settings", json={"preferences": {"LLM_PROVIDER": "bogus-ai"}})
    assert r.status_code == 400


def test_put_settings_clears_foreign_model_on_provider_change(client: TestClient) -> None:
    """A global model id from the old provider would 404 on every turn —
    drop it so the factory's 'pick one in the picker' error surfaces."""
    gc.update_global_config("LLM_MODEL", "gemini-2.5-pro")
    r = client.put("/api/settings", json={"preferences": {"LLM_PROVIDER": "groq"}})
    assert r.status_code == 200
    assert gc.load_global_config()["LLM_MODEL"] == ""
    assert settings.llm_model is None
    assert "LLM_MODEL" not in os.environ


def test_put_settings_mirrors_credential_to_env_and_settings(client: TestClient) -> None:
    """Keys saved from the dashboard must be visible to the picker and the
    factories immediately — the old path wrote auth.json only."""
    r = client.put(
        "/api/settings",
        json={"credentials": {"GROQ_API_KEY": "gsk-test-123", "GEMINI_API_KEY": "ai-test-456"}},
    )
    assert r.status_code == 200
    assert os.environ["GROQ_API_KEY"] == "gsk-test-123"
    assert os.environ["GEMINI_API_KEY"] == "ai-test-456"
    assert cs.get_credential("GROQ_API_KEY") == "gsk-test-123"
    assert settings.groq_api_key == "gsk-test-123"  # mapped field
    # GEMINI_API_KEY has no settings field — env is enough (key_for reads env).


def test_put_settings_rejects_unknown_credential(client: TestClient) -> None:
    r = client.put("/api/settings", json={"credentials": {"NOT_A_KEY": "x"}})
    assert r.status_code == 400


def test_put_settings_rejects_unknown_preference(client: TestClient) -> None:
    r = client.put("/api/settings", json={"preferences": {"LLM_MODEL": "x"}})
    assert r.status_code == 400  # the picker owns LLM_MODEL, not the settings panel


def test_put_settings_rejects_invalid_choice_value(client: TestClient) -> None:
    r = client.put("/api/settings", json={"preferences": {"TTS_PROVIDER": "yodeling"}})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# /api/llm/select — the picker's write path
# ---------------------------------------------------------------------------


def test_llm_select_requires_api_key(client: TestClient) -> None:
    model_id = mc.models("openrouter")[0]["id"]
    r = client.post("/api/llm/select", json={"provider": "openrouter", "model": model_id})
    assert r.status_code == 400
    assert "API key" in r.json()["detail"]


def test_llm_select_rejects_unknown_model(client: TestClient) -> None:
    r = client.post(
        "/api/llm/select",
        json={"provider": "openrouter", "model": "definitely-not-a-model", "api_key": "sk-test"},
    )
    assert r.status_code == 400
    assert "not a known" in r.json()["detail"]


def test_llm_select_applies_live(client: TestClient) -> None:
    model_id = mc.models("openrouter")[0]["id"]
    r = client.post(
        "/api/llm/select",
        json={"provider": "openrouter", "model": model_id, "api_key": "sk-test-123"},
    )
    assert r.status_code == 200
    config = gc.load_global_config()
    assert config["LLM_PROVIDER"] == "openrouter"
    assert config["LLM_MODEL"] == model_id
    assert os.environ["OPENROUTER_API_KEY"] == "sk-test-123"
    assert os.environ["LLM_PROVIDER"] == "openrouter"
    assert settings.llm_provider == "openrouter"
    assert settings.llm_model == model_id
