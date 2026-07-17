"""Factory module for instantiating the configured Speech-to-Text provider."""

from yumii.audio.stt_providers import GroqSTT, LocalSTT
from yumii.core.config import settings
from yumii.core.interfaces import BaseSTTProvider


def get_stt_provider() -> BaseSTTProvider:
    """Instantiate the correct STT provider based on configuration."""
    provider = settings.stt_provider.lower()

    if provider == "groq":
        return GroqSTT(api_key=settings.groq_api_key)
    elif provider == "vosk":
        from yumii.audio.vosk_provider import VoskSTT
        from yumii.audio.vosk_model import get_vosk_model_path
        
        model_path = get_vosk_model_path(settings.vosk_model_size)
        return VoskSTT(model_path=model_path)

    # Default to local — load from the GitHub-mirrored model directory.
    # ensure_models_ready has already downloaded it (with progress); this
    # resolves the path (or downloads as a fallback if somehow missing).
    from yumii.audio.whisper_model import get_whisper_model_dir

    model_dir = get_whisper_model_dir(settings.whisper_model_size)
    return LocalSTT(model_size=settings.whisper_model_size, model_dir=model_dir)
