"""Download faster-whisper models from Yumii's GitHub release (HF's CDN is blocked on some networks).

Extracts to ~/.yumii/models/whisper/<size>/; LocalSTT loads from there, so HF is never contacted.
"""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path
from typing import Callable

from yumii.core.downloads import download_file
from yumii.core.logging import get_logger

log = get_logger(__name__)

# Permanent release, separate from the app's v* tags (model files never change).
_RELEASE_BASE = (
    "https://github.com/CodeNeuron58/Yumii/releases/download/whisper-models-v1"
)

_SIZES = ("tiny", "base", "small")
# A model missing any of these loads but crashes on first transcribe — check completeness.
_REQUIRED_FILES = ("config.json", "model.bin", "tokenizer.json")

ProgressFn = Callable[[float], None]


def _models_root() -> Path:
    return Path.home() / ".yumii" / "models" / "whisper"


def model_dir_for(size: str) -> Path:
    return _models_root() / (size if size in _SIZES else "base")


def is_present(size: str) -> bool:
    """True only when a COMPLETE model is on disk for *size*."""
    d = model_dir_for(size)
    return all((d / f).exists() for f in _REQUIRED_FILES)


def purge(size: str) -> None:
    """Delete a partial/broken model so the next fetch re-downloads it."""
    d = model_dir_for(size)
    if d.exists():
        log.warning("whisper_model_purging", size=size, path=str(d))
        shutil.rmtree(d, ignore_errors=True)


def get_whisper_model_dir(
    size: str = "base", on_progress: ProgressFn | None = None
) -> str:
    """Return a ready model dir, downloading the zip from GitHub if missing (raises if incomplete)."""
    if size not in _SIZES:
        size = "base"
    target = model_dir_for(size)
    if is_present(size):
        return str(target)

    purge(size)  # clear any partial leftovers first
    target.mkdir(parents=True, exist_ok=True)

    url = f"{_RELEASE_BASE}/whisper-{size}.zip"
    zip_path = target.parent / f"whisper-{size}.zip"
    log.info("downloading_whisper_model", size=size, url=url)
    try:
        download_file(url, zip_path, progress=on_progress)
        with zipfile.ZipFile(str(zip_path)) as z:
            z.extractall(str(target))
    finally:
        if zip_path.exists():
            os.remove(str(zip_path))

    if not is_present(size):
        purge(size)
        raise RuntimeError(f"Whisper '{size}' download/extract incomplete")

    log.info("whisper_model_ready", size=size, path=str(target))
    return str(target)
