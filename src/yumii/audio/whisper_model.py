"""Download + resolve faster-whisper models from Yumii's own GitHub release.

Upstream, faster-whisper fetches its models from HuggingFace's CDN, which
is unreachable on some networks (regional blocks/throttling). Kokoro
already downloads reliably from a GitHub release, so the Whisper models
are mirrored the same way: a one-time GitHub Actions workflow
(``.github/workflows/publish-models.yml``) republishes the Systran
faster-whisper models (MIT) as GitHub release assets, and this helper
downloads + extracts the size the user needs into
``~/.yumii/models/whisper/<size>/``. ``LocalSTT`` then loads
``WhisperModel`` straight from that directory, so HuggingFace is never
contacted.
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

# The models live on a dedicated, permanent release (separate from the
# app's ``v*`` version tags — the model files never change).
_RELEASE_BASE = (
    "https://github.com/CodeNeuron58/Yumii/releases/download/whisper-models-v1"
)

_SIZES = ("tiny", "base", "small")
# Files faster-whisper needs to load a model. A model missing any of
# these loads but crashes deep in CTranslate2 on the first transcribe,
# so completeness is checked by their presence.
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
    """Return the local dir of a ready faster-whisper model, downloading
    it from Yumii's GitHub release if missing.

    ``on_progress`` (0..1) drives the first-run download bar — unlike the
    upstream HuggingFace path, a zip download gives a real percentage.
    Raises if the download or extraction can't produce a complete model,
    so the engine's retry loop can re-fetch.
    """
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
