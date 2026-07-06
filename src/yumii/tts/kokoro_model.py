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


def _download(url: str, target: Path) -> None:
    """Download *url* to *target* atomically (.part rename) so an
    interrupted download never leaves a truncated file that would be
    mistaken for a complete model on the next start."""
    part = target.with_suffix(target.suffix + ".part")
    log.info("downloading_kokoro_file", url=url, target=str(target))
    urllib.request.urlretrieve(url, str(part))
    os.replace(str(part), str(target))


def get_kokoro_model_paths(model_size: str = "int8") -> tuple[str, str]:
    """Return ``(model_path, voices_path)``, downloading files if needed."""
    if model_size not in KOKORO_MODELS:
        log.warning("invalid_kokoro_model_size_fallback", size=model_size)
        model_size = "fp32"

    models_dir = Path.home() / ".yumii" / "models" / "kokoro"
    models_dir.mkdir(parents=True, exist_ok=True)

    model_path = models_dir / KOKORO_MODELS[model_size]
    voices_path = models_dir / _VOICES_FILE

    if not model_path.exists():
        _download(f"{_RELEASE_BASE}/{KOKORO_MODELS[model_size]}", model_path)
    if not voices_path.exists():
        _download(f"{_RELEASE_BASE}/{_VOICES_FILE}", voices_path)

    log.info("kokoro_model_ready", model=str(model_path), voices=str(voices_path))
    return str(model_path), str(voices_path)
