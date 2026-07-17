"""Tests for the first-run flow: model readiness + turn-error surfacing.

No real downloads and no real LLM calls — the download functions and
WhisperModel are mocked, and error classification is pure.
"""

from __future__ import annotations

import pytest

from yumii.core import models
from yumii.core.engine import _classify_turn_error


# ── needs_download ─────────────────────────────────────────────────────


def test_needs_download_when_kokoro_missing(monkeypatch):
    from yumii.core import config

    monkeypatch.setattr(config.settings, "tts_provider", "Kokoro")
    monkeypatch.setattr(config.settings, "stt_provider", "groq")
    monkeypatch.setattr(models, "_kokoro_present", lambda: False)
    assert models.needs_download() is True


def test_needs_download_when_local_whisper_missing(monkeypatch):
    from yumii.core import config

    monkeypatch.setattr(config.settings, "tts_provider", "Kokoro")
    monkeypatch.setattr(config.settings, "stt_provider", "local")
    monkeypatch.setattr(models, "_kokoro_present", lambda: True)
    monkeypatch.setattr(models, "_whisper_present", lambda: False)
    assert models.needs_download() is True


def test_no_download_when_all_present(monkeypatch):
    from yumii.core import config

    monkeypatch.setattr(config.settings, "tts_provider", "Kokoro")
    monkeypatch.setattr(config.settings, "stt_provider", "local")
    monkeypatch.setattr(models, "_kokoro_present", lambda: True)
    monkeypatch.setattr(models, "_whisper_present", lambda: True)
    assert models.needs_download() is False


def test_cloud_providers_need_no_local_models(monkeypatch):
    from yumii.core import config

    # ElevenLabs TTS + Groq STT — nothing local to download.
    monkeypatch.setattr(config.settings, "tts_provider", "ElevenLabs")
    monkeypatch.setattr(config.settings, "stt_provider", "groq")
    assert models.needs_download() is False


# ── ensure_models_ready ────────────────────────────────────────────────


def test_ensure_downloads_kokoro_with_progress(monkeypatch):
    from yumii.core import config
    import yumii.tts.kokoro_model as km

    monkeypatch.setattr(config.settings, "tts_provider", "Kokoro")
    monkeypatch.setattr(config.settings, "stt_provider", "groq")
    monkeypatch.setattr(models, "_kokoro_present", lambda: False)

    def fake_paths(size, on_progress=None):
        if on_progress:
            on_progress(0.5)
            on_progress(1.0)
        return ("model", "voices")

    monkeypatch.setattr(km, "get_kokoro_model_paths", fake_paths)

    stages: list[tuple[str, float | None]] = []
    models.ensure_models_ready(lambda s, f: stages.append((s, f)))

    assert any(s == "Downloading her voice" for s, _ in stages)
    assert ("ready", 1.0) in stages


def test_ensure_downloads_local_whisper(monkeypatch):
    from yumii.core import config
    import faster_whisper

    monkeypatch.setattr(config.settings, "tts_provider", "Kokoro")
    monkeypatch.setattr(config.settings, "stt_provider", "local")
    monkeypatch.setattr(config.settings, "whisper_model_size", "base")
    monkeypatch.setattr(models, "_kokoro_present", lambda: True)  # skip TTS
    monkeypatch.setattr(models, "_whisper_present", lambda: False)
    monkeypatch.setattr(models, "_purge_whisper_cache", lambda: None)

    built = {}

    class FakeWhisper:
        def __init__(self, size, **kw):
            built["size"] = size

        def transcribe(self, audio, **kw):  # the readiness probe
            return iter([]), None

    monkeypatch.setattr(faster_whisper, "WhisperModel", FakeWhisper)

    stages: list[str] = []
    models.ensure_models_ready(lambda s, f: stages.append(s))

    assert built["size"] == "base"
    assert "Getting her ears ready" in stages
    assert "ready" in stages


# ── Partial-download protection (the real bug from the clean-machine run)


def _make_snapshot(root, files):
    snap = root / "snapshots" / "abc123"
    snap.mkdir(parents=True)
    for f in files:
        (snap / f).write_text("x")


def test_incomplete_cache_reads_as_absent(monkeypatch, tmp_path):
    """The exact real failure: model.bin + tokenizer landed, config.json
    didn't. HF calls that 'cached'; we must not."""
    _make_snapshot(tmp_path, ["model.bin", "tokenizer.json"])
    monkeypatch.setattr(models, "_whisper_cache_dir", lambda: tmp_path)
    assert models._whisper_present() is False


def test_complete_cache_reads_as_present(monkeypatch, tmp_path):
    _make_snapshot(tmp_path, ["model.bin", "tokenizer.json", "config.json"])
    monkeypatch.setattr(models, "_whisper_cache_dir", lambda: tmp_path)
    assert models._whisper_present() is True


def test_missing_cache_reads_as_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(models, "_whisper_cache_dir", lambda: tmp_path / "nope")
    assert models._whisper_present() is False


def test_unusable_model_purges_and_raises(monkeypatch):
    """A model that loads but can't transcribe must never reach 'ready' —
    it purges the cache and raises so the caller re-downloads."""
    from yumii.core import config
    import faster_whisper

    monkeypatch.setattr(config.settings, "tts_provider", "Kokoro")
    monkeypatch.setattr(config.settings, "stt_provider", "local")
    monkeypatch.setattr(models, "_kokoro_present", lambda: True)
    monkeypatch.setattr(models, "_whisper_present", lambda: False)

    purges: list[int] = []
    monkeypatch.setattr(models, "_purge_whisper_cache", lambda: purges.append(1))

    class BrokenWhisper:
        def __init__(self, *a, **kw):
            pass

        def transcribe(self, audio, **kw):
            raise RuntimeError(
                "[json.exception.type_error.305] cannot use operator[] "
                "with a string argument with null"
            )

    monkeypatch.setattr(faster_whisper, "WhisperModel", BrokenWhisper)

    stages: list[str] = []
    with pytest.raises(RuntimeError):
        models.ensure_models_ready(lambda s, f: stages.append(s))

    assert "ready" not in stages  # never declared ready
    assert len(purges) >= 2  # purged before the fetch AND after the bad probe


def test_ensure_is_noop_when_present(monkeypatch):
    from yumii.core import config

    monkeypatch.setattr(config.settings, "tts_provider", "Kokoro")
    monkeypatch.setattr(config.settings, "stt_provider", "local")
    monkeypatch.setattr(models, "_kokoro_present", lambda: True)
    monkeypatch.setattr(models, "_whisper_present", lambda: True)

    stages: list[str] = []
    models.ensure_models_ready(lambda s, f: stages.append(s))
    # Only the terminal "ready" — no download stages.
    assert stages == ["ready"]


# ── turn-error classification (never a silent hang) ────────────────────


@pytest.mark.parametrize(
    "message,expected",
    [
        ("Error 401 Unauthorized", "auth"),
        ("invalid api key provided", "auth"),
        ("this model requires a subscription", "auth"),
        ("429 Too Many Requests: rate limit exceeded", "quota"),
        ("insufficient quota for this request", "quota"),
        ("model is overloaded, try again", "quota"),
        ("Connection refused: getaddrinfo failed", "network"),
        ("request timed out after 30s", "network"),
        ("some totally unexpected explosion", "generic"),
    ],
)
def test_error_classification(message, expected):
    kind, text = _classify_turn_error(Exception(message))
    assert kind == expected
    assert text  # always a spoken/shown message


def test_error_message_is_user_facing():
    _, msg = _classify_turn_error(Exception("401"))
    assert "dashboard" in msg.lower()  # auth points the user to fix it
