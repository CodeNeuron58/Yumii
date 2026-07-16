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
from pathlib import Path
from typing import Callable

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
    """Best-effort check of faster-whisper's HF cache for the model.

    If unsure we return False, which only costs a brief "getting ready"
    flash — the actual instantiation is instant when the model really is
    cached.
    """
    repo = _WHISPER_REPOS.get(settings.whisper_model_size, _WHISPER_REPOS["base"])
    if os.environ.get("HF_HUB_CACHE"):
        cache = Path(os.environ["HF_HUB_CACHE"])
    elif os.environ.get("HF_HOME"):
        cache = Path(os.environ["HF_HOME"]) / "hub"
    else:
        cache = Path.home() / ".cache" / "huggingface" / "hub"
    marker = "models--" + repo.replace("/", "--")
    return (cache / marker).exists()


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
        from faster_whisper import WhisperModel

        WhisperModel(
            settings.whisper_model_size, device="cpu", compute_type="int8"
        )
        log.info("whisper_prefetched", size=settings.whisper_model_size)

    report("ready", 1.0)
