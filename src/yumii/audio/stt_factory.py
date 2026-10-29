"""Factory module for instantiating the configured Speech-to-Text provider."""

from yumii.core import providers
from yumii.core.config import settings
from yumii.core.interfaces import BaseSTTProvider


def get_stt_provider() -> BaseSTTProvider:
    """Instantiate the configured STT provider (unknown values fall back to local Whisper)."""
    return providers.resolve("stt", settings.stt_provider).build()
