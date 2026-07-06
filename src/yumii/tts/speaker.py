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
                "  Run 'yumii attune' or open ⚙️ Configure Senses and set a Voice ID.\n"
                "  Find your Voice ID at: https://elevenlabs.io/voice-library\n"
                "  It looks like this: 21m00Tcm4TlvDq8ikWAM\n"
            )
            raise ValueError(msg)

    async def stream_speak(self, text: str) -> AsyncGenerator[Any, None]:
        """Stream audio chunks from ElevenLabs.

        Yields, in order:
          1. ``{"type": "metadata", "sampleRate": 22050}`` — once,
             tells the frontend the sample rate and lets it open
             the audio context.
          2. A sequence of base64-encoded audio chunks as they
             arrive from ElevenLabs — one yield per chunk.

        The engine consumes these in the
        :func:`yumii.core.engine.YumiiEngine.tts_speaker_task` loop
        and broadcasts each as a WebSocket ``audio_chunk`` event.
        """
        if not text or not text.strip():
            return

        # Yield metadata first so the frontend can prepare its audio
        # context before the first chunk arrives.
        yield {"type": "metadata", "sampleRate": 22050}

        try:
            # text_to_speech.stream returns an iterator of raw audio
            # bytes. We base64-encode each chunk so the WebSocket
            # payload stays JSON-safe (the engine's broadcast_payload
            # uses json.dumps).
            # pcm_22050 = raw signed 16-bit LE samples. The frontend's
            # streaming decoder reinterprets chunks as PCM16, so the
            # format must stay PCM (MP3 here plays as static) and the
            # rate must match the metadata yield above.
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
                # base64-encode once, broadcast the chunk. The
                # frontend stitches chunks together by appending raw
                # bytes after base64-decoding.
                yield base64.b64encode(chunk).decode("ascii")
        except Exception as e:
            log.error("elevenlabs_stream_error", error=str(e), exc_info=True)
            # Re-raise so the engine's `except Exception` branch
            # sends a final error payload to the frontend.
            raise

    def speak(self, text: str, streaming: bool = False) -> tuple[str | None, float]:
        """Perform blocking synthesis and return base64 encoded audio.

        Kept for backwards-compatibility with the non-streaming
        fallback path in :func:`yumii.core.engine.YumiiEngine.tts_speaker_task`.
        """
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
