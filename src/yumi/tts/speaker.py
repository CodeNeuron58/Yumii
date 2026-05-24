import base64
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from yumi.core.config import settings


class YumiSpeaker:
    def __init__(self):
        self.client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        self.model_id = "eleven_multilingual_v2"

        # Read voice ID from config — never hardcode this.
        # Set via 'yumi attune' or ⚙️ Configure Senses → Voice Settings.
        self.voice_id = settings.elevenlabs_voice_id

        if not self.voice_id:
            raise ValueError(
                "\n\n  ❌  No ElevenLabs Voice ID configured.\n"
                "  Run 'yumi attune' or open ⚙️ Configure Senses and set a Voice ID.\n"
                "  Find your Voice ID at: https://elevenlabs.io/voice-library\n"
                "  It looks like this: 21m00Tcm4TlvDq8ikWAM\n"
            )

    def speak(self, text: str, play_local: bool = False):
        """
        Synthesizes text and returns (base64_mp3, duration_seconds) for the
        frontend WebSocket. Returns (None, 0.0) on any error.
        """
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

            # For mp3_22050_32 (32 kbps CBR), duration ≈ bytes / 4000
            duration = len(audio_data) / 4000.0

            if play_local:
                print(
                    "Warning: Local mp3 playback is not supported — "
                    "audio will play on the frontend only."
                )

            audio_base64 = base64.b64encode(audio_data).decode("utf-8")
            return audio_base64, duration

        except Exception as e:
            print(f"Error speaking response: {e}")
            return None, 0.0
