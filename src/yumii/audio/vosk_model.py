"""Helper for downloading and resolving Vosk model paths."""

import os
import zipfile
import urllib.request
from pathlib import Path

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

def get_vosk_model_path(model_size: str = "small") -> str:
    """Return the absolute path to the Vosk model directory, downloading it if necessary."""
    if model_size not in VOSK_MODELS:
        log.warning("invalid_vosk_model_size_fallback", size=model_size)
        model_size = "small"
        
    model_info = VOSK_MODELS[model_size]
    models_dir = Path.home() / ".yumii" / "models" / "vosk"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    target_dir = models_dir / model_info["dir_name"]
    
    if target_dir.exists() and target_dir.is_dir():
        return str(target_dir)
        
    log.info("downloading_vosk_model", size=model_size, url=model_info["url"])
    zip_path = models_dir / f"{model_info['dir_name']}.zip"
    
    # Download
    urllib.request.urlretrieve(model_info["url"], str(zip_path))
    
    # Extract
    log.info("extracting_vosk_model", zip_path=str(zip_path))
    with zipfile.ZipFile(str(zip_path), 'r') as zip_ref:
        zip_ref.extractall(str(models_dir))
        
    # Cleanup zip
    os.remove(str(zip_path))
    
    log.info("vosk_model_ready", path=str(target_dir))
    return str(target_dir)
