"""Download and resolve the Moonshine v2 model (sherpa-onnx offline decode).

Moonshine v2 base, English, int8-quantized (MIT) — the lightweight STT
tier for weak hardware. sherpa-onnx ships it offline-only; live partials
come from the shared rolling-window pattern.
"""

from __future__ import annotations

import shutil
import tarfile
from pathlib import Path

from yumii.core.downloads import download_file
from yumii.core.logging import get_logger

log = get_logger(__name__)

_ARCHIVE_NAME = "sherpa-onnx-moonshine-base-en-quantized-2026-02-27"
_URL = f"https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{_ARCHIVE_NAME}.tar.bz2"

# The v2 layout: one encoder + one merged decoder (.ort), loaded by
# sherpa_onnx.OfflineRecognizer.from_moonshine_v2. These MUST match the
# files MoonshineStreamingSTT opens — the old v1 names here made a good
# download look "incomplete", so it was purged and re-fetched forever.
_REQUIRED_FILES = (
    "tokens.txt",
    "encoder_model.ort",
    "decoder_model_merged.ort",
)


def _models_root() -> Path:
    return Path.home() / ".yumii" / "models" / "moonshine"


def model_dir() -> Path:
    return _models_root() / _ARCHIVE_NAME


def is_present() -> bool:
    """True only when a COMPLETE model is on disk."""
    d = model_dir()
    return all((d / f).exists() for f in _REQUIRED_FILES)


def purge() -> None:
    """Delete a partial/broken model so the next fetch re-downloads it."""
    d = model_dir()
    if d.exists():
        log.warning("moonshine_model_purging", path=str(d))
        shutil.rmtree(d, ignore_errors=True)


def get_moonshine_model_dir() -> str:
    """Factory entry point: resolve or download (self-healing, like the whisper path)."""
    return ensure()


def ensure(on_progress=None) -> str:
    """Return a ready model dir, downloading the archive if missing (raises if incomplete)."""
    target = model_dir()
    if is_present():
        return str(target)

    purge()  # clear any partial leftovers first

    archive_path = _models_root() / f"{_ARCHIVE_NAME}.tar.bz2"
    log.info("downloading_moonshine_model", url=_URL)
    download_file(_URL, archive_path, progress=on_progress)
    try:
        with tarfile.open(archive_path, "r:bz2") as tf:
            tf.extractall(_models_root(), filter="data")
    finally:
        archive_path.unlink(missing_ok=True)

    if not is_present():
        purge()
        raise RuntimeError("Moonshine download/extract incomplete")

    log.info("moonshine_model_ready", path=str(target))
    return str(target)
