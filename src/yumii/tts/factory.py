"""Factory for instantiating the configured TTS speaker."""

from yumii.core.config import settings
from yumii.core.interfaces import BaseSpeaker
from yumii.tts.camb_speaker import CambSpeaker
from yumii.tts.speaker import YumiiSpeaker


def get_speaker() -> BaseSpeaker:
    """Instantiate the correct TTS speaker based on configuration."""
    provider = settings.tts_provider

    if provider == "CAMB.ai":
        return CambSpeaker()

    # Default to ElevenLabs / YumiiSpeaker
    return YumiiSpeaker()
