"""Download Kokoro TTS model files to ~/.yumii/models/kokoro on first use.

fp32 (~325 MB) is the default: int8 measured ~3.7x slower on x86 CPUs (fallback kernels).
"""

import os
from pathlib import Path
from typing import Callable

from yumii.core.downloads import download_file
from yumii.core.logging import get_logger

log = get_logger(__name__)

_RELEASE_BASE = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
)

KOKORO_MODELS = {
    "int8": "kokoro-v1.0.int8.onnx",
    "fp32": "kokoro-v1.0.onnx",
}
_VOICES_FILE = "voices-v1.0.bin"

# on_progress(fraction 0..1) — used by the first-run download screen.
ProgressFn = Callable[[float], None]


def _band_progress(on_progress: ProgressFn | None, lo: float, hi: float):
    """Map a 0..1 download fraction into the [lo, hi] slice of the first-run bar."""
    if on_progress is None:
        return None
    return lambda frac: on_progress(lo + frac * (hi - lo))


def _download(url: str, target: Path, progress=None) -> None:
    """Atomic, timeout-bounded download (see yumii.core.downloads)."""
    log.info("downloading_kokoro_file", url=url, target=str(target))
    download_file(url, target, progress=progress)


def _bundled_paths(model_size: str) -> tuple[str, str] | None:
    """Return bundled model paths if the installer shipped them (YUMII_MODELS_DIR), else None."""
    root = os.environ.get("YUMII_MODELS_DIR")
    if not root:
        return None
    kdir = Path(root) / "kokoro"
    model = kdir / KOKORO_MODELS[model_size]
    voices = kdir / _VOICES_FILE
    if model.exists() and voices.exists():
        log.info("kokoro_model_bundled", model=str(model))
        return str(model), str(voices)
    return None


def get_kokoro_model_paths(
    model_size: str = "int8", on_progress: ProgressFn | None = None
) -> tuple[str, str]:
    """Return (model_path, voices_path), using bundled files or downloading (on_progress drives the bar)."""
    if model_size not in KOKORO_MODELS:
        log.warning("invalid_kokoro_model_size_fallback", size=model_size)
        model_size = "fp32"

    bundled = _bundled_paths(model_size)
    if bundled is not None:
        return bundled

    models_dir = Path.home() / ".yumii" / "models" / "kokoro"
    models_dir.mkdir(parents=True, exist_ok=True)

    model_path = models_dir / KOKORO_MODELS[model_size]
    voices_path = models_dir / _VOICES_FILE

    if not model_path.exists():
        _download(
            f"{_RELEASE_BASE}/{KOKORO_MODELS[model_size]}",
            model_path,
            _band_progress(on_progress, 0.0, 0.92),
        )
    if not voices_path.exists():
        _download(
            f"{_RELEASE_BASE}/{_VOICES_FILE}",
            voices_path,
            _band_progress(on_progress, 0.92, 1.0),
        )

    log.info("kokoro_model_ready", model=str(model_path), voices=str(voices_path))
    return str(model_path), str(voices_path)
