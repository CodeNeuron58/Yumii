"""Factory for instantiating the configured TTS speaker."""

from yumii.core import providers
from yumii.core.config import settings
from yumii.core.interfaces import BaseSpeaker


def get_speaker() -> BaseSpeaker:
    """Instantiate the configured TTS speaker (unknown values fall back to ElevenLabs)."""
    return providers.resolve("tts", settings.tts_provider).build()
