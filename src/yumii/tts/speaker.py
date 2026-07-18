"""ElevenLabs TTS (Text-to-Speech) provider for Yumii."""

from __future__ import annotations

import base64
from typing import Any, AsyncGenerator

from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs

from yumii.core.config import settings
from yumii.core.interfaces import BaseSpeaker

from yumii.core.logging import get_logger

log = get_logger(__name__)


class YumiiSpeaker(BaseSpeaker):
    """TTS implementation using the ElevenLabs cloud API."""

    def __init__(self) -> None:
        """Initialize the ElevenLabs client and verify voice configuration."""
        self.client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        self.model_id = "eleven_multilingual_v2"
        self.voice_id = settings.elevenlabs_voice_id

        if not self.voice_id:
            msg = (
                "\n\n  ❌  No ElevenLabs Voice ID configured.\n"
                "  Open the ⚙️ dashboard and set an ElevenLabs Voice ID.\n"
                "  Find your Voice ID at: https://elevenlabs.io/voice-library\n"
                "  It looks like this: 21m00Tcm4TlvDq8ikWAM\n"
            )
            raise ValueError(msg)

    async def stream_speak(self, text: str) -> AsyncGenerator[Any, None]:
        """Stream audio from ElevenLabs: first a metadata frame (sampleRate), then base64 PCM16 chunks."""
        if not text or not text.strip():
            return

        yield {"type": "metadata", "sampleRate": 22050}

        try:
            # pcm_22050 raw PCM16 — must stay PCM (MP3 plays as static) and match the metadata rate.
            audio_stream = self.client.text_to_speech.stream(
                voice_id=self.voice_id,
                output_format="pcm_22050",
                text=text,
                model_id=self.model_id,
                voice_settings=VoiceSettings(
                    stability=0.0,
                    similarity_boost=1.0,
                    style=0.0,
                    use_speaker_boost=True,
                ),
            )
            for chunk in audio_stream:
                if not chunk:
                    continue
                yield base64.b64encode(chunk).decode("ascii")
        except Exception as e:
            log.error("elevenlabs_stream_error", error=str(e), exc_info=True)
            # Re-raise so the engine sends a final error payload.
            raise

    def speak(self, text: str, streaming: bool = False) -> tuple[str | None, float]:
        """Blocking synthesis returning base64 audio (non-streaming fallback path)."""
        if not text:
            return None, 0.0

        log.debug("elevenlabs_synthesizing")
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
        except Exception as e:
            log.error("elevenlabs_tts_error", error=str(e), exc_info=True)
            return None, 0.0
        else:
            return audio_base64, duration
