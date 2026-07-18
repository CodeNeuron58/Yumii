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

    if provider == "Kokoro":
        # Lazy import — pulls onnxruntime/espeak and may trigger a model download.
        from yumii.tts.kokoro_speaker import KokoroSpeaker

        return KokoroSpeaker()

    # Default to ElevenLabs / YumiiSpeaker.
    return YumiiSpeaker()
