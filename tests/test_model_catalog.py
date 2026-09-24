"""Tests for the models.dev catalog: snapshot, filtering, wiring, live selection."""

import io
import json

import pytest

from yumii.core import model_catalog as mc
from yumii.core.model_catalog import (
    PROVIDER_WIRING,
    canonical_provider,
    get_model,
    get_wiring,
    models,
    providers,
    reload_catalog,
)


# ---------------------------------------------------------------------------
# Bundled snapshot
# ---------------------------------------------------------------------------


def test_bundled_snapshot_loads_all_wired_providers():
    reload_catalog()
    ids = {p["id"] for p in providers()}
    assert {"anthropic", "openai", "groq", "opencode", "google", "openrouter",
            "deepseek", "xai", "togetherai", "mistral", "ollama"} <= ids


def test_opencode_zen_free_models_are_pickable():
    zen = models("opencode")
    free = [m for m in zen if m["cost_in"] == 0 and m["cost_out"] == 0]
    assert free, "Zen free models missing from the snapshot"
    assert all(m["tool_call"] for m in zen), "Zen models must support tool calling"


def test_bundled_models_are_chat_only():
    # Whisper-class audio models must never appear as pickable minds.
    groq_ids = {m["id"] for m in models("groq")}
    assert groq_ids, "groq snapshot missing"
    assert not any("whisper" in i for i in groq_ids)
    assert "tts" not in " ".join(groq_ids)


def test_get_model_known_and_unknown():
    some = models("groq")[0]
    assert get_model("groq", some["id"])["id"] == some["id"]
    assert get_model("groq", "totally-not-real-9000") is None


def test_openrouter_is_the_big_aggregator():
    assert len(models("openrouter")) > 100


# ---------------------------------------------------------------------------
# Provider aliasing + wiring
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Ollama", "ollama"),
        ("GROQ", "groq"),
        ("together", "togetherai"),
        ("x.ai", "xai"),
        ("nonsense-ai", None),
    ],
)
def test_canonical_provider(raw: str, expected: str | None):
    assert canonical_provider(raw) == expected


def test_every_wired_provider_has_a_key_env():
    for pid, wiring in PROVIDER_WIRING.items():
        assert wiring.env_key.endswith("_API_KEY"), pid
        if wiring.kind == "openai-compatible":
            assert wiring.base_url, pid


# ---------------------------------------------------------------------------
# Refresh: models.dev fetch -> filtered user snapshot (fake network)
# ---------------------------------------------------------------------------


_FULL = {
    "groq": {
        "doc": "https://groq.example",
        "models": {
            "llama-chat": {"id": "llama-chat", "name": "Llama Chat", "tool_call": True,
                           "modalities": {"input": ["text"], "output": ["text"]}},
            "whisper-big": {"id": "whisper-big", "modalities": {"input": ["audio"], "output": ["text"]}},
        },
    },
    "mystery-provider": {"models": {"m1": {}}},
}


class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_refresh_writes_filtered_user_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(
        mc.urllib.request, "urlopen", lambda req, timeout: _FakeResp(json.dumps(_FULL).encode())
    )
    target = tmp_path / "model-catalog.json"
    count = mc.refresh_catalog(target=target)

    assert count == 1  # whisper filtered, mystery provider not wired
    data = json.loads(target.read_text(encoding="utf-8"))
    assert set(data["providers"]["groq"]["models"]) == {"llama-chat"}
    assert "mystery-provider" not in data["providers"]


def test_broken_user_file_falls_back_to_bundled(tmp_path, monkeypatch):
    bad = tmp_path / "model-catalog.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(mc, "_USER_FILE", bad)
    reload_catalog()
    try:
        assert providers(), "bundled snapshot must still serve"
    finally:
        reload_catalog()


# ---------------------------------------------------------------------------
# Ollama live tags
# ---------------------------------------------------------------------------


def test_ollama_tag_parsing():
    data = {"models": [{"name": "minimax-m3"}, {"model": "llama3:8b"}, {"name": ""}]}
    out = mc._parse_ollama_tags(data)
    assert [m["id"] for m in out] == ["minimax-m3", "llama3:8b"]


# ---------------------------------------------------------------------------
# Google: mind filter + live ListModels
# ---------------------------------------------------------------------------


def test_google_snapshot_shows_chat_minds_only():
    ids = {m["id"] for m in models("google")}
    assert ids, "google snapshot missing"
    # real chat models survive…
    assert "gemini-2.5-flash" in ids
    # …image gen / TTS / Live audio / research / computer-use never appear
    joined = " ".join(ids)
    assert not any(x in joined for x in ("-image", "-tts", "live", "transcribe",
                                         "computer-use", "deep-research"))


def test_google_get_model_rejects_non_minds():
    assert get_model("google", "gemini-2.5-flash") is not None
    assert get_model("google", "gemini-3.1-flash-lite-image") is None


@pytest.mark.parametrize(
    "mid,expected",
    [
        ("gemini-3.8-flash", True),
        ("gemma-3-27b-it", True),
        ("gemini-3.1-flash-lite-image", False),   # Nano Banana image gen
        ("gemini-2.5-flash-preview-tts", False),  # TTS
        ("gemini-3.1-flash-live-preview", False),  # Live API audio
        ("gemini-3.5-transcribe", False),
        ("gemini-2.5-computer-use-preview-10-2025", False),
        ("deep-research-max-preview-04-2026", False),
        ("text-embedding-004", False),
    ],
)
def test_is_chat_mind(mid: str, expected: bool):
    assert mc._is_chat_mind(mid) is expected


_GOOGLE_LIST = {
    "models": [
        {"name": "models/gemini-3.8-flash", "displayName": "Gemini 3.8 Flash",
         "inputTokenLimit": 1048576, "outputTokenLimit": 65536,
         "supportedGenerationMethods": ["generateContent", "countTokens"]},
        {"name": "models/gemini-2.5-flash-preview-tts", "displayName": "TTS",
         "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-embedding-001",
         "supportedGenerationMethods": ["embedContent"]},
        {"name": "models/imagen-4.0-generate-001",
         "supportedGenerationMethods": ["predict"]},
    ],
}


def test_google_listmodels_parsing():
    out = mc._parse_google_models(
        _GOOGLE_LIST, {"gemini-3.8-flash": {"tool_call": True, "reasoning": True}}
    )
    ids = [m["id"] for m in out]
    assert ids == ["gemini-3.8-flash"]  # TTS + embeddings + imagen filtered
    m = out[0]
    assert m["name"] == "Gemini 3.8 Flash"
    assert m["tool_call"] is True and m["reasoning"] is True
    assert m["context"] == 1048576 and m["max_output"] == 65536


def test_google_listmodels_unknown_model_defaults():
    data = {"models": [{"name": "models/gemini-9.9-flash", "displayName": "Gemini 9.9 Flash",
                        "supportedGenerationMethods": ["generateContent"]}]}
    (m,) = mc._parse_google_models(data)
    assert m["id"] == "gemini-9.9-flash"
    assert m["tool_call"] is True and m["reasoning"] is None


# ---------------------------------------------------------------------------
# LLM wiring (agent/llm.py) — no network, constructors only
# ---------------------------------------------------------------------------


from yumii.agent.llm import _build_base_llm, _resolve_model  # noqa: E402
from yumii.core.config import settings  # noqa: E402


def test_llm_model_setting_wins_over_everything(monkeypatch):
    monkeypatch.setattr(settings, "llm_model", "the-picked-model")
    monkeypatch.setattr(settings, "llm_provider", "groq")
    assert _resolve_model("groq") == "the-picked-model"


def test_unknown_provider_falls_back_to_groq(monkeypatch):
    monkeypatch.setattr(settings, "llm_model", None)
    monkeypatch.setattr(settings, "llm_provider", "nonsense-ai")
    monkeypatch.setattr(settings, "groq_model", "legacy-behavior")
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    llm = _build_base_llm()
    assert llm.model_name == "legacy-behavior"


def test_openai_compatible_provider_builds_with_base_url(monkeypatch):
    monkeypatch.setattr(settings, "llm_model", "deepseek-chat")
    monkeypatch.setattr(settings, "llm_provider", "deepseek")
    monkeypatch.setattr(mc, "key_for", lambda p: "test-key")
    llm = _build_base_llm()
    assert llm.model_name == "deepseek-chat"
    assert "deepseek" in (llm.openai_api_base or "")


def test_missing_key_raises_actionable_error(monkeypatch):
    monkeypatch.setattr(settings, "llm_model", "some-model")
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    monkeypatch.setattr(mc, "key_for", lambda p: None)
    with pytest.raises(ValueError, match="Model picker"):
        _build_base_llm()


def test_ollama_needs_no_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_model", None)
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "ollama_model", "minimax-m3")
    monkeypatch.setattr(settings, "ollama_api_key", None)
    llm = _build_base_llm()
    assert llm.model == "minimax-m3"


def test_hardcoded_models_are_gone():
    import inspect

    from yumii.agent import llm as llm_mod

    src = inspect.getsource(llm_mod._build_base_llm)
    assert "gpt-4o" not in src
    assert "claude-3-5-sonnet" not in src


def test_wiring_covers_every_catalog_provider():
    wiring_ids = set(PROVIDER_WIRING)
    assert get_wiring("ollama") is not None
    assert wiring_ids == set(p["id"] for p in providers())


def test_cheap_model_is_always_a_real_catalog_id():
    """The cheap pick must be derived from the snapshot — never a hardcoded
    id that can silently retire (the old Groq fallback died exactly that way)."""
    for provider in ("openai", "anthropic", "google", "groq"):
        pick = mc.cheap_model_for(provider)
        if pick is not None:
            assert pick in {m["id"] for m in mc.models(provider)}


def test_cheap_model_prefers_marked_small_tiers():
    pick = mc.cheap_model_for("google")
    assert pick is not None
    assert any(p in pick.lower() for p in ("flash", "mini", "nano", "lite"))


def test_cheap_model_none_without_snapshot_knowledge():
    # Ollama's live tag list has no snapshot slice; nonsense isn't a provider.
    assert mc.cheap_model_for("ollama") is None
    assert mc.cheap_model_for("nonsense-ai") is None


def test_background_llm_prefers_the_cheap_tier(monkeypatch):
    from yumii.agent.llm import build_background_llm

    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(mc, "cheap_model_for", lambda p: "test-mini" if p == "openai" else None)
    monkeypatch.setattr(mc, "key_for", lambda p: "test-key")
    assert build_background_llm().model_name == "test-mini"


def test_background_llm_falls_back_to_the_selected_model(monkeypatch):
    from yumii.agent.llm import build_background_llm

    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_model", "the-selected-model")
    monkeypatch.setattr(mc, "cheap_model_for", lambda p: None)
    monkeypatch.setattr(mc, "key_for", lambda p: "test-key")
    assert build_background_llm().model_name == "the-selected-model"
