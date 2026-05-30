"""Factory for instantiating the configured TTS speaker."""
from yumi.core.config import settings
from yumi.core.interfaces import BaseSpeaker
from yumi.tts.speaker import YumiSpeaker
from yumi.tts.camb_speaker import CambSpeaker

def get_speaker() -> BaseSpeaker:
    """Instantiate the correct TTS speaker based on configuration."""
    provider = settings.tts_provider

    if provider == "CAMB.ai":
        return CambSpeaker()

    # Default to ElevenLabs / YumiSpeaker
    return YumiSpeaker()
