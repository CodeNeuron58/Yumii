"""Helper for downloading and resolving Vosk model paths."""

import os
import shutil
import zipfile
from pathlib import Path

from yumii.core.downloads import download_file
from yumii.core.logging import get_logger

log = get_logger(__name__)

VOSK_MODELS = {
    "small": {
        "url": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
        "dir_name": "vosk-model-small-en-us-0.15",
    },
    "medium": {
        "url": "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22-lgraph.zip",
        "dir_name": "vosk-model-en-us-0.22-lgraph",
    },
}

# A partial extract loads then crashes mid-turn — treat these as the
# completeness bar and purge anything missing them.
_REQUIRED_ENTRIES = ("conf", "am")


def get_vosk_model_path(model_size: str = "small") -> str:
    """Return the absolute path to the Vosk model directory, downloading it if necessary."""
    if model_size not in VOSK_MODELS:
        log.warning("invalid_vosk_model_size_fallback", size=model_size)
        model_size = "small"

    model_info = VOSK_MODELS[model_size]
    models_dir = Path.home() / ".yumii" / "models" / "vosk"
    models_dir.mkdir(parents=True, exist_ok=True)

    target_dir = models_dir / model_info["dir_name"]

    if target_dir.exists():
        if all((target_dir / f).exists() for f in _REQUIRED_ENTRIES):
            return str(target_dir)
        # a crashed extract must not be cached forever
        log.warning("vosk_model_incomplete_purging", path=str(target_dir))
        shutil.rmtree(target_dir, ignore_errors=True)

    log.info("downloading_vosk_model", size=model_size, url=model_info["url"])
    zip_path = models_dir / f"{model_info['dir_name']}.zip"

    download_file(model_info["url"], zip_path)

    log.info("extracting_vosk_model", zip_path=str(zip_path))
    with zipfile.ZipFile(str(zip_path), 'r') as zip_ref:
        zip_ref.extractall(str(models_dir))

    os.remove(str(zip_path))

    if not all((target_dir / f).exists() for f in _REQUIRED_ENTRIES):
        shutil.rmtree(target_dir, ignore_errors=True)
        raise RuntimeError(f"Vosk '{model_size}' download/extract incomplete")

    log.info("vosk_model_ready", path=str(target_dir))
    return str(target_dir)
