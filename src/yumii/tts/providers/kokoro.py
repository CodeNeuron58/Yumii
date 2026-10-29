"""Kokoro-82M (local ONNX) — free, offline, the fresh-install voice."""

from __future__ import annotations

import os
from pathlib import Path

from yumii.core.config import settings
from yumii.core.logging import get_logger
from yumii.core.providers import ProgressReport, ProviderSpec, register

log = get_logger(__name__)

register("tts", "Kokoro", __name__, label="Kokoro (local, free)")


def build(spec: ProviderSpec):
    # Lazy import — pulls onnxruntime/espeak and may trigger a model download.
    from yumii.tts.kokoro_speaker import KokoroSpeaker

    return KokoroSpeaker()


def present(spec: ProviderSpec) -> bool:
    from yumii.tts.kokoro_model import KOKORO_MODELS, _VOICES_FILE

    size = settings.kokoro_model_size if settings.kokoro_model_size in KOKORO_MODELS else "fp32"
    # A bundled install (YUMII_MODELS_DIR) counts as present.
    if os.environ.get("YUMII_MODELS_DIR"):
        root = Path(os.environ["YUMII_MODELS_DIR"]) / "kokoro"
        if (root / KOKORO_MODELS[size]).exists() and (root / _VOICES_FILE).exists():
            return True
    kdir = Path.home() / ".yumii" / "models" / "kokoro"
    return (kdir / KOKORO_MODELS[size]).exists() and (kdir / _VOICES_FILE).exists()


def provision(spec: ProviderSpec, report: ProgressReport) -> None:
    from yumii.tts.kokoro_model import get_kokoro_model_paths

    stage = "Downloading her voice"
    report(stage, 0.0)
    get_kokoro_model_paths(settings.kokoro_model_size or "fp32", on_progress=lambda f: report(stage, f))
    log.info("kokoro_prefetched")
