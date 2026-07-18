"""Vosk STT provider with streaming partial results."""

import json
from typing import Any

from vosk import Model, KaldiRecognizer

from yumii.core.interfaces import BaseSTTProvider
from yumii.core.logging import get_logger

log = get_logger(__name__)


class VoskSTT(BaseSTTProvider):
    """Streaming Vosk STT."""

    def __init__(self, model_path: str):
        """Initialize Vosk recognizer."""
        log.info("vosk_loading", model_path=model_path)
        self.model = Model(model_path)
        self.rec = KaldiRecognizer(self.model, 16000)
        self.rec.SetWords(True)
        self.rec.SetPartialWords(True)
        self.accumulated_text = ""
        log.info("vosk_ready")

    def process_chunk(self, pcm16_bytes: bytes) -> dict | None:
        """Feed an audio chunk; return a partial-transcript event or None."""
        if self.rec.AcceptWaveform(pcm16_bytes):
            # Silence finalized a sub-utterance — MUST grab Result() now or the text is lost.
            result = json.loads(self.rec.Result())
            text = self._filter_confident(result)
            if text:
                self.accumulated_text += (" " if self.accumulated_text else "") + text

            if self.accumulated_text:
                return {"type": "partial_transcript", "text": self.accumulated_text}
        else:
            partial = json.loads(self.rec.PartialResult())
            current_partial = partial.get("partial", "").strip()

            full_text = self.accumulated_text
            if current_partial:
                full_text += (" " if full_text else "") + current_partial

            if full_text:
                return {"type": "partial_transcript", "text": full_text}

        return None

    def get_final(self) -> str | None:
        """Called when Silero VAD detects silence."""
        result = json.loads(self.rec.FinalResult())
        text = self._filter_confident(result)

        full_text = self.accumulated_text
        if text:
            full_text += (" " if full_text else "") + text

        # Reset recognizer and accumulator for the next full sentence.
        self.accumulated_text = ""
        self.rec = KaldiRecognizer(self.model, 16000)
        self.rec.SetWords(True)
        self.rec.SetPartialWords(True)

        return full_text.strip() or None

    def _filter_confident(self, result: dict) -> str | None:
        """Return the aggregated text; deliberately no per-word confidence gate (it dropped real words)."""
        return (result.get("text", "") or "").strip() or None

    def transcribe(self, audio_data: Any) -> str | None:
        """Fallback for non-streaming usage."""
        self.rec.AcceptWaveform(audio_data.tobytes())
        return self.get_final()
