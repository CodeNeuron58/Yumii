from yumi.core.config import settings
from yumi.core.interfaces import BaseSpeaker
from yumi.tts.speaker import YumiSpeaker
from yumi.tts.camb_speaker import CambSpeaker

def get_speaker() -> BaseSpeaker:
    """Factory to instantiate the correct TTS speaker based on the active configuration."""
    provider = settings.tts_provider

    if provider == "CAMB.ai":
        return CambSpeaker()

    # Default to ElevenLabs / YumiSpeaker
    return YumiSpeaker()
