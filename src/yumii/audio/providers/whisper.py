"""Local Whisper (faster-whisper, CPU int8) — private and offline, the fresh-install ear."""

from __future__ import annotations

from typing import Any

from yumii.core.config import settings
from yumii.core.logging import get_logger
from yumii.core.providers import ProgressReport, ProviderSpec, register

log = get_logger(__name__)

register("stt", "local", __name__, label="Local Whisper (private, offline)")


def build(spec: ProviderSpec):
    from yumii.audio.stt_providers import LocalSTT
    from yumii.audio.whisper_model import get_whisper_model_dir

    # Resolve the GitHub-mirrored dir (or fallback-download it).
    size = settings.whisper_model_size
    return LocalSTT(model_size=size, model_dir=get_whisper_model_dir(size))


def present(spec: ProviderSpec) -> bool:
    """True only when a COMPLETE model is on disk (partial downloads crash on transcribe)."""
    from yumii.audio import whisper_model

    return whisper_model.is_present(settings.whisper_model_size)


def _probe(model: Any) -> None:
    """Force a 1-second transcribe to prove a fresh model works (loading isn't enough)."""
    import numpy as np

    t = np.arange(16000, dtype=np.float32) / 16000.0
    probe = (0.05 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    segments, _ = model.transcribe(probe, language="en", beam_size=1)
    list(segments)  # the generator is where generate() actually runs


def provision(spec: ProviderSpec, report: ProgressReport) -> None:
    from yumii.audio.whisper_model import get_whisper_model_dir, purge

    stage = "Getting her ears ready"
    report(stage, 0.0)
    size = settings.whisper_model_size
    model_dir = get_whisper_model_dir(size, on_progress=lambda f: report(stage, f))
    # Loading isn't enough — probe before declaring ready; purge on failure so retry re-fetches.
    from faster_whisper import WhisperModel

    try:
        model = WhisperModel(model_dir, device="cpu", compute_type="int8")
        _probe(model)
    except Exception:
        purge(size)
        raise
    log.info("whisper_prefetched", size=size)
