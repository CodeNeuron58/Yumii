"""Concrete implementations of Speech-to-Text (STT) providers.

Includes a local CPU-based `faster-whisper` provider and a cloud-based `Groq` provider.
"""


import numpy as np

from yumii.core.interfaces import BaseSTTProvider

from yumii.core.logging import get_logger
log = get_logger(__name__)


class LocalSTT(BaseSTTProvider):
    """Transcription using faster-whisper on CPU."""

    def __init__(self, model_size: str = "base") -> None:
        """Initialize the local Whisper model."""
        from faster_whisper import WhisperModel

        log.info("whisper_loading", model_size=model_size)
        self._whisper = WhisperModel(model_size, device="cpu", compute_type="int8")
        log.info("whisper_ready", model_size=model_size)

    def transcribe(self, audio_data: np.ndarray) -> str | None:
        """Transcribe an audio array using the local Whisper model."""
        # faster-whisper expects float32 in [-1, 1]
        audio_float = audio_data.astype(np.float32) / 32768.0

        segments, _ = self._whisper.transcribe(
            audio_float,
            beam_size=1,
            condition_on_previous_text=False,
            suppress_blank=True,
            # Threshold from original pipeline
            no_speech_threshold=0.45,
        )

        text_parts = []
        for segment in segments:
            if segment.no_speech_prob > 0.45:
                continue
            text_parts.append(segment.text)

        return "".join(text_parts).strip() or None


class GroqSTT(BaseSTTProvider):
    """Transcription using Groq's Whisper API."""

    def __init__(self, api_key: str) -> None:
        """Initialize the Groq API client."""
        from groq import Groq

        self._groq_client = Groq(api_key=api_key)
        log.info("groq_stt_ready", model="whisper-large-v3-turbo")

    def transcribe(self, audio_data: np.ndarray) -> str | None:
        """Transcribe an audio array using the Groq Whisper API."""
        # Helper to encode as WAV bytes
        import io
        import wave

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)  # RATE
            wf.writeframes(audio_data.tobytes())

        try:
            result = self._groq_client.audio.transcriptions.create(
                file=("audio.wav", buf.getvalue()),
                model="whisper-large-v3-turbo",
                response_format="text",
                language="en",
            )
            return result.strip() if result else None
        except Exception as e:
            log.error("groq_stt_error", error=str(e), exc_info=True)
            return None
