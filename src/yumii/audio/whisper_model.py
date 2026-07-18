"""Download faster-whisper models from Yumii's GitHub release (HF's CDN is blocked on some networks).

Extracts to ~/.yumii/models/whisper/<size>/; LocalSTT loads from there, so HF is never contacted.
"""

from __future__ import annotations

import os
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

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


def _hook(on_progress: ProgressFn | None):
    if on_progress is None:
        return None

    def hook(block_num: int, block_size: int, total_size: int) -> None:
        if total_size > 0:
            on_progress(min(1.0, (block_num * block_size) / total_size))

    return hook


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
    part = target.parent / f"whisper-{size}.zip.part"
    log.info("downloading_whisper_model", size=size, url=url)
    try:
        urllib.request.urlretrieve(url, str(part), reporthook=_hook(on_progress))
        with zipfile.ZipFile(str(part)) as z:
            z.extractall(str(target))
    finally:
        if part.exists():
            os.remove(str(part))

    if not is_present(size):
        purge(size)
        raise RuntimeError(f"Whisper '{size}' download/extract incomplete")

    log.info("whisper_model_ready", size=size, path=str(target))
    return str(target)
