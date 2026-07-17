"""Concrete implementations of Speech-to-Text (STT) providers.

Includes a local CPU-based `faster-whisper` provider and a cloud-based `Groq` provider.
"""


import numpy as np

from yumii.core.interfaces import BaseSTTProvider

from yumii.core.logging import get_logger
log = get_logger(__name__)

# Confidence gates for the cloud (Groq) Whisper path. Whisper will happily
# transcribe humming, singing, and background noise into words; these
# thresholds drop segments it isn't confident are real speech, mirroring the
# `no_speech_prob` filter the local path already applies.
NO_SPEECH_THRESHOLD = 0.6        # drop if Whisper thinks it isn't speech
MIN_AVG_LOGPROB = -1.0           # drop low-confidence guesses (humming / gibberish)
MAX_COMPRESSION_RATIO = 2.4      # drop repetitive hallucinations (common on music)


def _seg_field(seg: object, key: str, default: object) -> object:
    """Read a Whisper segment field whether Groq returns dicts or objects."""
    if isinstance(seg, dict):
        return seg.get(key, default)
    return getattr(seg, key, default)


class LocalSTT(BaseSTTProvider):
    """Transcription using faster-whisper on CPU.

    Loads the model from a local directory (Yumii mirrors the
    faster-whisper models on its own GitHub release — see
    ``audio/whisper_model.py`` — so HuggingFace is never contacted). If
    no ``model_dir`` is given it falls back to the size string, which
    lets faster-whisper resolve/download from HuggingFace itself.
    """

    def __init__(self, model_size: str = "base", model_dir: str | None = None) -> None:
        """Initialize the local Whisper model."""
        from faster_whisper import WhisperModel

        source = model_dir or model_size
        log.info("whisper_loading", source=source)
        self._whisper = WhisperModel(source, device="cpu", compute_type="int8")
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
                # verbose_json gives per-segment confidence so we can reject
                # non-speech (humming, singing, noise) instead of voicing it.
                response_format="verbose_json",
                language="en",
            )
        except Exception as e:
            log.error("groq_stt_error", error=str(e), exc_info=True)
            return None

        segments = getattr(result, "segments", None) or []

        # Older API / no segments — fall back to the top-level text.
        if not segments:
            text = (getattr(result, "text", "") or "").strip()
            return text or None

        kept: list[str] = []
        for seg in segments:
            text = str(_seg_field(seg, "text", "") or "").strip()
            if not text:
                continue
            no_speech = float(_seg_field(seg, "no_speech_prob", 0.0))
            avg_logprob = float(_seg_field(seg, "avg_logprob", 0.0))
            comp_ratio = float(_seg_field(seg, "compression_ratio", 1.0))

            # Logged at info so a user watching the console can tell a
            # discarded utterance apart from a slow one.
            if no_speech > NO_SPEECH_THRESHOLD:
                log.info("stt_dropped", reason="no_speech", no_speech=round(no_speech, 2), text=text[:40])
                continue
            if avg_logprob < MIN_AVG_LOGPROB:
                log.info("stt_dropped", reason="low_confidence", avg_logprob=round(avg_logprob, 2), text=text[:40])
                continue
            if comp_ratio > MAX_COMPRESSION_RATIO:
                log.info("stt_dropped", reason="repetitive", compression_ratio=round(comp_ratio, 2), text=text[:40])
                continue
            kept.append(text)

        combined = " ".join(kept).strip()
        return combined or None
