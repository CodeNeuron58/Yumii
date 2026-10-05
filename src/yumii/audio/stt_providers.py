"""STT providers: local faster-whisper (CPU) and cloud Groq Whisper."""


import time

import numpy as np

from yumii.core.interfaces import BaseSTTProvider

from yumii.core.logging import get_logger

log = get_logger(__name__)

# Confidence gates for Groq Whisper — drop humming/noise it would transcribe into words.
NO_SPEECH_THRESHOLD = 0.6        # drop if Whisper thinks it isn't speech
MIN_AVG_LOGPROB = -1.0           # drop low-confidence guesses (humming / gibberish)
MAX_COMPRESSION_RATIO = 2.4      # drop repetitive hallucinations (common on music)


def _seg_field(seg: object, key: str, default: object) -> object:
    """Read a Whisper segment field whether Groq returns dicts or objects."""
    if isinstance(seg, dict):
        return seg.get(key, default)
    return getattr(seg, key, default)


class LocalSTT(BaseSTTProvider):
    """faster-whisper on CPU, loaded from a local dir (mirrored on GitHub; HF never contacted).

    Streaming partials: Whisper can't stream, so while the user speaks we
    re-decode the last few seconds every couple of seconds — small batch jobs
    that make the text appear live. The final decode at end-of-turn always
    covers the whole utterance, so what reaches memory and the transcript is
    exactly as accurate as the batch path.
    """

    # Rolling window and re-decadence interval. A 4s window on int8 CPU costs
    # ~200-400ms per decode; asking every 2s of new audio keeps Whisper busy
    # ~15-20% of one core, only while the user is speaking.
    _PARTIAL_WINDOW_SEC = 4.0
    _PARTIAL_INTERVAL_SEC = 2.0
    _RATE = 16000
    _MIN_UTTERANCE_SEC = 0.7  # same floor as the batch path

    def __init__(self, model_size: str = "base", model_dir: str | None = None) -> None:
        """Initialize the local Whisper model."""
        from faster_whisper import WhisperModel

        source = model_dir or model_size
        log.info("whisper_loading", source=source)
        self._whisper = WhisperModel(source, device="cpu", compute_type="int8")
        log.info("whisper_ready", model_size=model_size)
        self._utterance: list[np.ndarray] = []
        self._tail = np.empty(0, dtype=np.int16)
        self._frames_since_partial = 0
        self._last_partial = ""

    def _decode(self, audio_float: np.ndarray) -> str | None:
        segments, _ = self._whisper.transcribe(
            audio_float,
            beam_size=1,
            condition_on_previous_text=False,
            suppress_blank=True,
            no_speech_threshold=0.45,
        )

        text_parts = []
        for segment in segments:
            if segment.no_speech_prob > 0.45:
                continue
            text_parts.append(segment.text)

        return "".join(text_parts).strip() or None

    def transcribe(self, audio_data: np.ndarray) -> str | None:
        """Transcribe an audio array using the local Whisper model."""
        # faster-whisper expects float32 in [-1, 1].
        return self._decode(audio_data.astype(np.float32) / 32768.0)

    def process_chunk(self, pcm16_bytes: bytes) -> dict | None:
        """Streaming interface: consume one frame; emit a live partial when
        enough new audio has accumulated since the last one."""
        frame = np.frombuffer(pcm16_bytes, dtype=np.int16)
        self._utterance.append(frame)
        self._tail = np.concatenate([self._tail, frame])[
            -int(self._PARTIAL_WINDOW_SEC * self._RATE):
        ]
        self._frames_since_partial += len(frame)
        if self._frames_since_partial < int(self._PARTIAL_INTERVAL_SEC * self._RATE):
            return None
        self._frames_since_partial = 0

        text = self._decode(self._tail.astype(np.float32) / 32768.0)
        if not text or text == self._last_partial:
            return None  # unchanged — the orb already shows it
        self._last_partial = text
        return {"type": "partial_transcript", "text": text}

    def get_final(self) -> str | None:
        """End of turn: decode the FULL utterance (full context — this is the
        text that enters memory and the transcript), then reset streaming
        state. Called automatically at end-of-turn, on the mute sentinel, and
        at capture start (residue discard)."""
        frames, self._utterance = self._utterance, []
        self._tail = np.empty(0, dtype=np.int16)
        self._frames_since_partial = 0
        self._last_partial = ""

        total = sum(len(f) for f in frames)
        if total < int(self._MIN_UTTERANCE_SEC * self._RATE):
            return None
        audio = np.concatenate(frames).astype(np.float32) / 32768.0
        return self._decode(audio)


class GroqSTT(BaseSTTProvider):
    """Transcription using Groq's Whisper API."""

    def __init__(self, api_key: str) -> None:
        """Initialize the Groq API client."""
        from groq import Groq

        self._groq_client = Groq(api_key=api_key)
        log.info("groq_stt_ready", model="whisper-large-v3-turbo")

    def transcribe(self, audio_data: np.ndarray) -> str | None:
        """Transcribe an audio array using the Groq Whisper API."""
        import io
        import wave

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)  # RATE
            wf.writeframes(audio_data.tobytes())

        result = None
        last_error: Exception | None = None
        for attempt in (1, 2):
            try:
                result = self._groq_client.audio.transcriptions.create(
                    file=("audio.wav", buf.getvalue()),
                    model="whisper-large-v3-turbo",
                    # verbose_json gives per-segment confidence for the gates below.
                    response_format="verbose_json",
                    language="en",
                    # SDK default is minutes — a stalled call must not wedge
                    # the single listener task while mic audio buffers.
                    timeout=15.0,
                )
                break
            except Exception as exc:
                last_error = exc
                lowered = str(exc).lower()
                transient = any(
                    s in lowered
                    for s in ("429", "rate limit", "overloaded", "timed out",
                              "timeout", "503", "502", "connection")
                )
                if attempt == 1 and transient:
                    log.warning("groq_stt_retrying", attempt=attempt, error=str(exc)[:200])
                    time.sleep(1.5)  # runs off-loop via asyncio.to_thread
                    continue
                log.error("groq_stt_error", error=str(exc), exc_info=True)
                return None
        if result is None:
            log.error("groq_stt_error", error=str(last_error))
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

            # Log drops at info so a discarded utterance is distinguishable from a slow one.
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
