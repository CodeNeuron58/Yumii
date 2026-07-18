"""Download local STT + TTS models on first launch (VAD is bundled; only the LLM is cloud)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from yumii.core.config import settings
from yumii.core.logging import get_logger

log = get_logger(__name__)

# on_progress(stage_label, fraction); fraction is 0..1 or None for indeterminate.
ProgressCb = Callable[[str, "float | None"], None]


def _kokoro_present() -> bool:
    from yumii.tts.kokoro_model import KOKORO_MODELS, _VOICES_FILE

    # A bundled install (YUMII_MODELS_DIR) counts as present.
    if os.environ.get("YUMII_MODELS_DIR"):
        root = Path(os.environ["YUMII_MODELS_DIR"]) / "kokoro"
        size = settings.kokoro_model_size if settings.kokoro_model_size in KOKORO_MODELS else "fp32"
        if (root / KOKORO_MODELS[size]).exists() and (root / _VOICES_FILE).exists():
            return True

    size = settings.kokoro_model_size if settings.kokoro_model_size in KOKORO_MODELS else "fp32"
    kdir = Path.home() / ".yumii" / "models" / "kokoro"
    return (kdir / KOKORO_MODELS[size]).exists() and (kdir / _VOICES_FILE).exists()


def _whisper_present() -> bool:
    """True only when a COMPLETE Whisper model is on disk (partial downloads crash on transcribe)."""
    from yumii.audio import whisper_model

    return whisper_model.is_present(settings.whisper_model_size)


def _probe_whisper(model: Any) -> None:
    """Force a 1-second transcribe to prove a fresh model works (loading isn't enough)."""
    import numpy as np

    t = np.arange(16000, dtype=np.float32) / 16000.0
    probe = (0.05 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    segments, _ = model.transcribe(probe, language="en", beam_size=1)
    list(segments)  # the generator is where generate() actually runs


def needs_download() -> bool:
    """True if any configured local model (Kokoro / local Whisper) is missing."""
    if settings.tts_provider == "Kokoro" and not _kokoro_present():
        return True
    if settings.stt_provider.lower() == "local" and not _whisper_present():
        return True
    return False


def ensure_models_ready(on_progress: ProgressCb | None = None) -> None:
    """Download any missing local models. Blocking — call in a thread; raises on failure."""

    def report(stage: str, frac: float | None = None) -> None:
        if on_progress is None:
            return
        try:
            on_progress(stage, frac)
        except Exception:
            pass

    if settings.tts_provider == "Kokoro" and not _kokoro_present():
        from yumii.tts.kokoro_model import get_kokoro_model_paths

        report("Downloading her voice", 0.0)
        size = settings.kokoro_model_size or "fp32"
        get_kokoro_model_paths(
            size, on_progress=lambda f: report("Downloading her voice", f)
        )
        log.info("kokoro_prefetched")

    if settings.stt_provider.lower() == "local" and not _whisper_present():
        from yumii.audio.whisper_model import get_whisper_model_dir, purge

        report("Getting her ears ready", 0.0)
        size = settings.whisper_model_size
        model_dir = get_whisper_model_dir(
            size, on_progress=lambda f: report("Getting her ears ready", f)
        )
        # Loading isn't enough — probe before declaring ready; purge on failure so retry re-fetches.
        from faster_whisper import WhisperModel

        try:
            model = WhisperModel(model_dir, device="cpu", compute_type="int8")
            _probe_whisper(model)
        except Exception:
            purge(size)
            raise
        log.info("whisper_prefetched", size=size)

    report("ready", 1.0)
