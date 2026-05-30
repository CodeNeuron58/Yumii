"""ElevenLabs TTS (Text-to-Speech) provider for Yumi."""
import base64
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from yumi.core.config import settings
from yumi.core.interfaces import BaseSpeaker
from typing import AsyncGenerator, Any

class YumiSpeaker(BaseSpeaker):
    """TTS implementation using the ElevenLabs cloud API."""

    def __init__(self):
        """Initialize the ElevenLabs client and verify voice configuration."""
        self.client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        self.model_id = "eleven_multilingual_v2"
        self.voice_id = settings.elevenlabs_voice_id

        if not self.voice_id:
            raise ValueError(
                "\n\n  ❌  No ElevenLabs Voice ID configured.\n"
                "  Run 'yumi attune' or open ⚙️ Configure Senses and set a Voice ID.\n"
                "  Find your Voice ID at: https://elevenlabs.io/voice-library\n"
                "  It looks like this: 21m00Tcm4TlvDq8ikWAM\n"
            )

    async def stream_speak(self, text: str) -> AsyncGenerator[Any, None]:
        """Synthesize text and yield audio metadata followed by the audio data."""
        audio_base64, duration = self.speak(text)
        if audio_base64:
            # Yield metadata first to satisfy the engine's expectations
            yield {"type": "metadata", "sampleRate": 22050} # ElevenLabs default
            # Yield the full audio as a single chunk
            yield audio_base64
        else:
            print("Error: ElevenLabs synthesis failed in stream_speak.")

    def speak(self, text: str, streaming: bool = False) -> tuple[str | None, float]:
        """Perform blocking synthesis and return base64 encoded audio."""
        if not text:
            return None, 0.0

        print("Synthesizing voice with ElevenLabs...")
        try:
            response_chunks = self.client.text_to_speech.convert(
                voice_id=self.voice_id,
                output_format="mp3_22050_32",
                text=text,
                model_id=self.model_id,
                voice_settings=VoiceSettings(
                    stability=0.0,
                    similarity_boost=1.0,
                    style=0.0,
                    use_speaker_boost=True,
                ),
            )

            audio_data = b"".join([chunk for chunk in response_chunks if chunk])
            duration = len(audio_data) / 4000.0
            audio_base64 = base64.b64encode(audio_data).decode("utf-8")
            return audio_base64, duration

        except Exception as e:
            print(f"Error speaking response: {e}")
            return None, 0.0
