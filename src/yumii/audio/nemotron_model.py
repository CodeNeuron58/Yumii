"""Download and resolve the NVIDIA Nemotron Speech Streaming models (sherpa-onnx).

True cache-aware streaming ASR — each frame is processed once, unlike the
rolling-window Whisper re-decode. The "en" variant is the English default;
"multi" is Nemotron 3.5 ASR (40 locales, auto language detection).
"""

from __future__ import annotations

import shutil
import tarfile
from pathlib import Path

from yumii.core.downloads import download_file
from yumii.core.logging import get_logger

log = get_logger(__name__)

# sherpa-onnx release archives (int8, 560ms chunk — best accuracy/latency
# balance per the October 2026 streaming-STT study in research-stt.md).
_VARIANTS = {
    "en": "sherpa-onnx-nemotron-speech-streaming-en-0.6b-560ms-int8-2026-04-25",
    "multi": "sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-560ms-int8-2026-06-11",
}
_RELEASE_BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models"

# A partial extract loads then fails mid-sentence — treat these as the
# completeness bar and purge anything missing them.
_REQUIRED_FILES = ("tokens.txt", "encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx")


def _models_root() -> Path:
    return Path.home() / ".yumii" / "models" / "nemotron"


def model_dir(variant: str = "en") -> Path:
    return _models_root() / _VARIANTS[variant]


def is_present(variant: str = "en") -> bool:
    """True only when a COMPLETE model is on disk."""
    d = model_dir(variant)
    return all((d / f).exists() for f in _REQUIRED_FILES)


def purge(variant: str = "en") -> None:
    """Delete a partial/broken model so the next fetch re-downloads it."""
    d = model_dir(variant)
    if d.exists():
        log.warning("nemotron_model_purging", path=str(d))
        shutil.rmtree(d, ignore_errors=True)


def get_nemotron_model_dir(variant: str = "en") -> str:
    """Factory entry point: resolve or download (self-healing, like the whisper path)."""
    return ensure(variant)


def ensure(variant: str = "en", on_progress=None) -> str:
    """Return a ready model dir, downloading the archive if missing (raises if incomplete)."""
    archive = _VARIANTS[variant]
    target = model_dir(variant)
    if is_present(variant):
        return str(target)

    purge(variant)  # clear any partial leftovers first

    url = f"{_RELEASE_BASE}/{archive}.tar.bz2"
    archive_path = _models_root() / f"{archive}.tar.bz2"
    log.info("downloading_nemotron_model", variant=variant, url=url)
    download_file(url, archive_path, progress=on_progress)
    try:
        with tarfile.open(archive_path, "r:bz2") as tf:
            tf.extractall(_models_root(), filter="data")
    finally:
        archive_path.unlink(missing_ok=True)

    if not is_present(variant):
        purge(variant)
        raise RuntimeError(f"Nemotron '{variant}' download/extract incomplete")

    log.info("nemotron_model_ready", path=str(target))
    return str(target)
