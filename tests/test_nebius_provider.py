"""Nebius Token Factory: NVIDIA Nemotron as Yumii's default mind.

No network: the live listing is exercised through its parser, and the
LangChain client is only constructed (never called).
"""

import pytest

from yumii.core import model_catalog as mc

SUPER = "nvidia/nemotron-3-super-120b-a12b"
NANO = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"


@pytest.fixture
def no_snapshot(monkeypatch):
    """models.dev has no Token Factory entry — the curated line-up answers."""
    monkeypatch.setattr(mc, "_get", lambda user_file=None: {})


def test_wiring_is_openai_compatible_with_thinking_off():
    w = mc.get_wiring("nebius")
    assert w is not None and w.kind == "openai-compatible"
    assert w.env_key == "NEBIUS_API_KEY"
    assert w.base_url == "https://api.tokenfactory.nebius.com/v1"
    # A reasoning pass costs seconds before the first spoken word.
    assert w.extra_body == {"chat_template_kwargs": {"enable_thinking": False}}


def test_aliases_resolve_to_nebius():
    assert mc.canonical_provider("TokenFactory") == "nebius"
    assert mc.canonical_provider("Nebius") == "nebius"


def test_curated_nemotron_lineup(no_snapshot):
    ids = [m["id"] for m in mc.models("nebius")]
    assert ids[0] == SUPER == mc.NEBIUS_DEFAULT_MODEL
    assert NANO in ids
    assert all(m["tool_call"] for m in mc.models("nebius"))
    assert all(i.startswith("nvidia/") for i in ids)


def test_get_model_knows_nemotron(no_snapshot):
    assert mc.get_model("nebius", SUPER)["tool_call"] is True
    assert mc.get_model("nebius", "nvidia/not-a-model") is None


def test_background_work_runs_on_nano(no_snapshot):
    assert mc.cheap_model_for("nebius") == NANO


def test_parse_live_listing_keeps_tool_capable_chat_models():
    data = {"data": [
        {"id": "Qwen/Qwen3-235B", "supported_features": ["tools"], "context_length": 32768,
         "pricing": {"prompt": "0.0000002", "completion": "0.0000006"}},
        {"id": SUPER, "supported_features": ["tools", "reasoning"], "context_length": 262144,
         "pricing": {"prompt": "0.0000003", "completion": "0.0000009"}},
        {"id": "BAAI/bge-embedding", "supported_features": ["tools"]},  # not a chat mind
        {"id": "some/no-tools-model", "supported_features": []},        # can't bind tools
    ]}

    out = mc._parse_nebius_models(data)

    assert [m["id"] for m in out] == [SUPER, "Qwen/Qwen3-235B"]  # NVIDIA first
    assert out[0]["cost_in"] == 0.3 and out[0]["cost_out"] == 0.9  # per 1M, like models.dev
    assert out[0]["reasoning"] is True and out[1]["reasoning"] is False


def _use_nebius(monkeypatch, *, key: str | None = "test-key", model: str | None = None):
    from yumii.core.config import settings

    monkeypatch.setattr(settings, "llm_provider", "nebius")
    monkeypatch.setattr(settings, "llm_model", model)
    if key:
        monkeypatch.setenv("NEBIUS_API_KEY", key)
    else:
        monkeypatch.delenv("NEBIUS_API_KEY", raising=False)


def test_mind_defaults_to_nemotron_super_with_thinking_off(monkeypatch, no_snapshot):
    from yumii.agent.llm import _build_base_llm

    _use_nebius(monkeypatch)
    llm = _build_base_llm()

    assert llm.model_name == SUPER
    assert "tokenfactory.nebius.com" in str(llm.openai_api_base)
    assert llm.extra_body == {"chat_template_kwargs": {"enable_thinking": False}}


def test_background_llm_is_nano(monkeypatch, no_snapshot):
    from yumii.agent.llm import build_background_llm

    _use_nebius(monkeypatch)
    assert build_background_llm().model_name == NANO


def test_picker_selection_wins_over_the_default(monkeypatch, no_snapshot):
    from yumii.agent.llm import _build_base_llm

    _use_nebius(monkeypatch, model="nvidia/Nemotron-3-Ultra-550b-a55b")
    assert _build_base_llm().model_name == "nvidia/Nemotron-3-Ultra-550b-a55b"


def test_missing_key_is_an_actionable_error(monkeypatch, no_snapshot):
    from yumii.agent.llm import _build_base_llm

    _use_nebius(monkeypatch, key=None)
    with pytest.raises(ValueError, match="Nebius Token Factory"):
        _build_base_llm()


def test_fresh_install_default_is_nebius():
    from yumii.core.config import Settings

    assert Settings.model_fields["llm_provider"].default == "nebius"


def test_keys_are_allowlisted_in_auth_json():
    from yumii.core.credential_store import CREDENTIAL_KEYS

    assert {"NEBIUS_API_KEY", "TAVILY_API_KEY"} <= CREDENTIAL_KEYS
