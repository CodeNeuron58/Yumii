"""Factory module for instantiating the configured Speech-to-Text provider."""

from yumii.audio.stt_providers import GroqSTT, LocalSTT
from yumii.core.config import settings
from yumii.core.interfaces import BaseSTTProvider


def get_stt_provider() -> BaseSTTProvider:
    """Instantiate the correct STT provider based on configuration."""
    provider = settings.stt_provider.lower()

    if provider == "groq":
        return GroqSTT(api_key=settings.groq_api_key)

    # Default to local
    return LocalSTT(model_size=settings.whisper_model_size)
