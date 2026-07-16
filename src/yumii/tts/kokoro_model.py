"""Helper for downloading and resolving Kokoro TTS model files.

Mirrors :mod:`yumii.audio.vosk_model`: files live under
``~/.yumii/models/kokoro`` and are fetched on first use. Two model
variants are offered — ``fp32`` (~325 MB, default) and ``int8``
(~92 MB). Counterintuitively, int8 measured ~3.7x SLOWER than fp32 on
x86 CPUs (quantized ops hit onnxruntime fallback kernels), so fp32 is
the default despite the bigger download.
"""

import os
import urllib.request
from pathlib import Path
from typing import Callable

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


def _hook_into(on_progress: ProgressFn | None, lo: float, hi: float):
    """Map ``urlretrieve``'s (block, size, total) into a [lo, hi] fraction."""
    if on_progress is None:
        return None

    def hook(block_num: int, block_size: int, total_size: int) -> None:
        if total_size <= 0:
            return
        frac = min(1.0, (block_num * block_size) / total_size)
        on_progress(lo + frac * (hi - lo))

    return hook


def _download(url: str, target: Path, reporthook=None) -> None:
    """Download *url* to *target* atomically (.part rename) so an
    interrupted download never leaves a truncated file that would be
    mistaken for a complete model on the next start."""
    part = target.with_suffix(target.suffix + ".part")
    log.info("downloading_kokoro_file", url=url, target=str(target))
    urllib.request.urlretrieve(url, str(part), reporthook=reporthook)
    os.replace(str(part), str(target))


def _bundled_paths(model_size: str) -> tuple[str, str] | None:
    """Return bundled model paths if the installer shipped them.

    The desktop installer bundles the Kokoro files and the Tauri shell
    points ``YUMII_MODELS_DIR`` at ``<resources>/models`` — so a fresh
    install needs no download or setup. Returns ``None`` when unset or
    incomplete (dev / source runs), which falls through to the
    download path below.
    """
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
    """Return ``(model_path, voices_path)``, using bundled files or
    downloading if needed. ``on_progress`` (0..1) drives the first-run
    download screen; the model file is the bulk of it, the voices file
    a short tail."""
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
            _hook_into(on_progress, 0.0, 0.92),
        )
    if not voices_path.exists():
        _download(
            f"{_RELEASE_BASE}/{_VOICES_FILE}",
            voices_path,
            _hook_into(on_progress, 0.92, 1.0),
        )

    log.info("kokoro_model_ready", model=str(model_path), voices=str(voices_path))
    return str(model_path), str(voices_path)
