"""Local model readiness — download STT + TTS models before first use.

VAD (Silero) ships bundled in the wheel, so it never downloads. Whisper
(STT, when local) and Kokoro (TTS) are fetched on first launch — with a
progress screen in the orb — instead of stalling mid-conversation the
first time she tries to listen or speak. A fresh install is
"everything local except the brain": only the LLM key is needed.

The engine runs :func:`ensure_models_ready` on a worker thread at boot
and reports progress via ``/api/status`` so the orb can show it.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Callable

from yumii.core.config import settings
from yumii.core.logging import get_logger

log = get_logger(__name__)

# on_progress(stage_label, fraction) — fraction is 0..1, or None for an
# indeterminate stage (no clean byte-progress available).
ProgressCb = Callable[[str, "float | None"], None]

# faster-whisper pulls these HF repos on first WhisperModel(size) call.
_WHISPER_REPOS = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
}

# Files a usable faster-whisper model must have. A download that drops
# mid-flight (flaky network) can leave model.bin + tokenizer without
# config.json — the model then LOADS fine but crashes deep inside
# CTranslate2 on the first real transcribe ("cannot use operator[] with
# a string argument with null", because the absent config reads as
# null). Worse, HuggingFace hands that partial snapshot back as "cached"
# on every retry, so it never self-heals. We verify completeness
# ourselves.
_WHISPER_REQUIRED_FILES = ("config.json", "model.bin", "tokenizer.json")


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


def _hf_cache_root() -> Path:
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"])
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def _whisper_cache_dir() -> Path:
    """The HF cache folder for the configured Whisper model."""
    repo = _WHISPER_REPOS.get(settings.whisper_model_size, _WHISPER_REPOS["base"])
    return _hf_cache_root() / ("models--" + repo.replace("/", "--"))


def _whisper_present() -> bool:
    """True only when a COMPLETE Whisper model is cached.

    Deliberately not "does the folder exist" — a partial download leaves
    a folder that HF calls cached but that can't transcribe. Requiring
    the real files means an incomplete cache re-downloads instead of
    silently giving the user broken ears forever.
    """
    snapshots = _whisper_cache_dir() / "snapshots"
    if not snapshots.is_dir():
        return False
    return any(
        all((snap / f).exists() for f in _WHISPER_REQUIRED_FILES)
        for snap in snapshots.iterdir()
        if snap.is_dir()
    )


def _purge_whisper_cache() -> None:
    """Delete a partial model so the next fetch re-downloads it whole."""
    target = _whisper_cache_dir()
    if target.exists():
        log.warning("whisper_cache_incomplete_purging", path=str(target))
        shutil.rmtree(target, ignore_errors=True)


def _probe_whisper(model: Any) -> None:
    """Prove a freshly-downloaded model can actually transcribe.

    Loading is not enough: an incomplete model loads happily and only
    dies inside CTranslate2's generate on the user's first word. Force
    that code path here — while we can still purge and re-fetch — with
    a second of tone. Raises if the model is unusable.
    """
    import numpy as np

    t = np.arange(16000, dtype=np.float32) / 16000.0
    probe = (0.05 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    segments, _ = model.transcribe(probe, language="en", beam_size=1)
    list(segments)  # the generator is where generate() actually runs


def needs_download() -> bool:
    """Cheap check: is any configured local model missing?

    Only the local providers matter — a cloud STT (Groq) or cloud TTS
    needs no local model.
    """
    if settings.tts_provider == "Kokoro" and not _kokoro_present():
        return True
    if settings.stt_provider.lower() == "local" and not _whisper_present():
        return True
    return False


def ensure_models_ready(on_progress: ProgressCb | None = None) -> None:
    """Download any missing local models. Blocking — call in a thread.

    Never raises for a provider that isn't configured local; a download
    failure propagates so the caller can surface it (the orb retries).
    """

    def report(stage: str, frac: float | None = None) -> None:
        if on_progress is None:
            return
        try:
            on_progress(stage, frac)
        except Exception:
            pass

    # TTS: Kokoro (~330 MB, the big one) — real % via urlretrieve hook.
    if settings.tts_provider == "Kokoro" and not _kokoro_present():
        from yumii.tts.kokoro_model import get_kokoro_model_paths

        report("Downloading her voice", 0.0)
        size = settings.kokoro_model_size or "fp32"
        get_kokoro_model_paths(
            size, on_progress=lambda f: report("Downloading her voice", f)
        )
        log.info("kokoro_prefetched")

    # STT: local Whisper — faster-whisper downloads on instantiation and
    # gives no clean byte hook, so this stage is indeterminate.
    if settings.stt_provider.lower() == "local" and not _whisper_present():
        report("Getting her ears ready", None)

        # A leftover PARTIAL download must be purged first: HuggingFace
        # would otherwise return that broken snapshot as "cached" on
        # every retry, so the download never actually re-runs and she
        # ends up permanently deaf with an opaque crash on each word.
        _purge_whisper_cache()

        from faster_whisper import WhisperModel

        model = WhisperModel(
            settings.whisper_model_size, device="cpu", compute_type="int8"
        )
        # Loading proves nothing — make it transcribe before we call it
        # ready. If the download was incomplete this raises, and the
        # caller's retry loop purges and re-fetches.
        try:
            _probe_whisper(model)
        except Exception:
            _purge_whisper_cache()
            raise
        log.info("whisper_prefetched", size=settings.whisper_model_size)

    report("ready", 1.0)
