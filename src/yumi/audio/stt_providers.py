from typing import Any
import numpy as np
from yumi.core.interfaces import BaseSTTProvider

class LocalSTT(BaseSTTProvider):
    """
    Transcription using faster-whisper on CPU.
    """
    def __init__(self, model_size: str = "base"):
        from faster_whisper import WhisperModel
        print(f"Loading Whisper model ({model_size}) on CPU...")
        self._whisper = WhisperModel(model_size, device="cpu", compute_type="int8")
        print(f"Whisper model ({model_size}) loaded.")

    def transcribe(self, audio_data: np.ndarray) -> str | None:
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
    """
    Transcription using Groq's Whisper API.
    """
    def __init__(self, api_key: str):
        from groq import Groq
        self._groq_client = Groq(api_key=api_key)
        print("Groq Whisper STT ready (whisper-large-v3-turbo).")

    def transcribe(self, audio_data: np.ndarray) -> str | None:
        # Helper to encode as WAV bytes
        import io
        import wave
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000) # RATE
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
            print(f"❌ Groq STT error: {e}")
            return None
