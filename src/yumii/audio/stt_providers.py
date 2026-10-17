"""STT providers: local faster-whisper (CPU), cloud Groq Whisper, Moonshine v2, and true-streaming Nemotron."""

import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

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


# ---------------------------------------------------------------------------
# Shared streaming pattern for offline decoders
# ---------------------------------------------------------------------------


class _RollingWindowSTT(BaseSTTProvider):
    """Live partials for decoders that cannot stream (Whisper, Moonshine...).

    Whisper-style models can't stream — so while the user speaks, re-decode
    the last few seconds every couple of seconds (small batch jobs,
    diff-suppressed partials), and decode the FULL utterance at end-of-turn
    so what reaches memory and the transcript has full context.
    Subclasses implement :meth:`_decode` (float32 audio in [-1, 1] → text).

    Partials are strictly opportunistic. They decode on a background thread
    (one at a time, skipped while busy) so capture never waits on them, and
    they switch themselves off when the hardware can't afford them: Whisper
    pads every decode to 30s, so on a laptop CPU a 4s partial costs ~2.2s
    and a decode can't be cancelled — an in-flight partial delays the final
    decode by whatever it has left. Live text is a nicety; a slow end of
    turn is not.
    """

    _PARTIAL_WINDOW_SEC = 4.0
    _PARTIAL_INTERVAL_SEC = 2.0
    _RATE = 16000
    _MIN_UTTERANCE_SEC = 0.7
    # A partial may cost at most this fraction of the interval; this many
    # over-budget partials in a row switch partials off for the provider's
    # lifetime (one slow decode during a CPU spike shouldn't).
    _MAX_PARTIAL_COST = 0.5
    _SLOW_PARTIALS_TO_DISABLE = 2
    _clock = staticmethod(time.perf_counter)

    def __init__(self) -> None:
        self._utterance: list[np.ndarray] = []
        self._tail = np.empty(0, dtype=np.int16)
        self._frames_since_partial = 0
        self._last_partial = ""
        self._executor: ThreadPoolExecutor | None = None
        self._partial_future: Future | None = None
        self._epoch = 0  # bumped per utterance; stale partials are dropped
        self._partials_enabled = True
        self._slow_partials = 0

    def _decode(self, audio_float: np.ndarray) -> str | None:
        raise NotImplementedError

    def _partial_executor(self) -> ThreadPoolExecutor:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="stt-partial")
        return self._executor

    def _timed_decode(self, audio_float: np.ndarray, epoch: int) -> tuple[str | None, float, int]:
        start = self._clock()
        text = self._decode(audio_float)
        return text, self._clock() - start, epoch

    def _harvest_partial(self) -> dict | None:
        """Collect a finished background partial, if any (never waits)."""
        future = self._partial_future
        if future is None or not future.done():
            return None
        self._partial_future = None
        try:
            text, elapsed, epoch = future.result()
        except Exception:
            log.warning("stt_partial_decode_failed", exc_info=True)
            return None

        budget = self._MAX_PARTIAL_COST * self._PARTIAL_INTERVAL_SEC
        self._slow_partials = self._slow_partials + 1 if elapsed > budget else 0
        if self._slow_partials >= self._SLOW_PARTIALS_TO_DISABLE and self._partials_enabled:
            self._partials_enabled = False
            log.info(
                "stt_partials_disabled_too_slow",
                decode_sec=round(elapsed, 2), budget_sec=budget,
            )

        if epoch != self._epoch or not text or text == self._last_partial:
            return None  # stale (previous utterance), empty, or unchanged
        self._last_partial = text
        return {"type": "partial_transcript", "text": text}

    def process_chunk(self, pcm16_bytes: bytes) -> dict | None:
        frame = np.frombuffer(pcm16_bytes, dtype=np.int16)
        self._utterance.append(frame)
        self._tail = np.concatenate([self._tail, frame])[
            -int(self._PARTIAL_WINDOW_SEC * self._RATE):
        ]
        self._frames_since_partial += len(frame)

        event = self._harvest_partial()
        due = self._frames_since_partial >= int(self._PARTIAL_INTERVAL_SEC * self._RATE)
        if due and self._partials_enabled and self._partial_future is None:
            self._frames_since_partial = 0
            window = self._tail.astype(np.float32) / 32768.0
            self._partial_future = self._partial_executor().submit(
                self._timed_decode, window, self._epoch
            )
            event = self._harvest_partial() or event  # an inline executor finishes at once
        return event

    def reset(self) -> None:
        """Drop the current utterance without decoding it (mute, aborted capture)."""
        self._utterance = []
        self._tail = np.empty(0, dtype=np.int16)
        self._frames_since_partial = 0
        self._last_partial = ""
        self._epoch += 1
        self._partial_future = None  # its result would be stale; let it finish unseen

    def get_final(self) -> str | None:
        """End of turn: decode the WHOLE utterance. Blocks — call it off the event loop."""
        frames = self._utterance
        self.reset()

        total = sum(len(f) for f in frames)
        if total < int(self._MIN_UTTERANCE_SEC * self._RATE):
            return None
        audio = np.concatenate(frames).astype(np.float32) / 32768.0
        # Peak-normalize like the batch path does (quiet mics shift
        # Whisper's log-mel features and cost accuracy).
        peak = float(np.max(np.abs(audio)))
        if peak > 0:
            audio = audio * (0.9 / peak)
        return self._decode(audio)


class LocalSTT(_RollingWindowSTT):
    """faster-whisper on CPU, loaded from a local dir (mirrored on GitHub; HF never contacted).

    Live partials via the shared rolling-window pattern; the end-of-turn
    decode always covers the whole utterance, so what reaches memory and the
    transcript is exactly as accurate as the batch path.
    """

    def __init__(self, model_size: str = "base", model_dir: str | None = None) -> None:
        """Initialize the local Whisper model."""
        from faster_whisper import WhisperModel

        super().__init__()
        source = model_dir or model_size
        log.info("whisper_loading", source=source)
        self._whisper = WhisperModel(source, device="cpu", compute_type="int8")
        log.info("whisper_ready", model_size=model_size)
        self._calibrate_partials()

    def _calibrate_partials(self) -> None:
        """Decide up front whether live partials are affordable on this machine.

        Whisper pads every decode to 30s, so one decode of a second of silence
        costs what a live partial will (base on an i5-13500H: 2.07s vs 2.20s
        for a real 4s window). Over budget → partials start switched off, so
        no turn pays to find out. Also warms the model before the first turn.
        """
        start = self._clock()
        self._decode(np.zeros(self._RATE, dtype=np.float32))
        cost = self._clock() - start
        budget = self._MAX_PARTIAL_COST * self._PARTIAL_INTERVAL_SEC
        if cost > budget:
            self._partials_enabled = False
            log.info("stt_partials_off_too_slow", decode_sec=round(cost, 2), budget_sec=budget)

    def transcribe(self, audio_data: np.ndarray) -> str | None:
        """Transcribe an audio array using the local Whisper model."""
        # faster-whisper expects float32 in [-1, 1].
        return self._decode(audio_data.astype(np.float32) / 32768.0)

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


class MoonshineStreamingSTT(_RollingWindowSTT):
    """Moonshine v2 via sherpa-onnx's offline decoder — the lightweight tier.

    The v2 models (123M params, MIT) beat Whisper large-v3 on WER and decode
    far faster on CPU; sherpa-onnx ships them offline-only, so live partials
    come from the shared rolling-window pattern.
    """

    _PARTIAL_WINDOW_SEC = 6.0  # v2's sliding-window encoder likes more context
    _PARTIAL_INTERVAL_SEC = 2.0

    def __init__(self, model_dir: str) -> None:
        import sherpa_onnx

        super().__init__()
        d = Path(model_dir)
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_moonshine_v2(
            encoder=str(d / "encoder_model.ort"),
            decoder=str(d / "decoder_model_merged.ort"),
            tokens=str(d / "tokens.txt"),
            num_threads=1,
        )
        log.info("moonshine_stt_ready")

    def transcribe(self, audio_data: np.ndarray) -> str | None:
        """Fallback for non-streaming usage: one offline decode."""
        return self._decode(audio_data.astype(np.float32) / 32768.0)

    def _decode(self, audio_float: np.ndarray) -> str | None:
        stream = self._recognizer.create_stream()
        stream.accept_waveform(self._RATE, audio_float)
        self._recognizer.decode_stream(stream)
        return (stream.result.text or "").strip() or None


class NemotronStreamingSTT(BaseSTTProvider):
    """True streaming STT: NVIDIA Nemotron Speech Streaming via sherpa-onnx.

    A cache-aware transducer — every frame is processed ONCE (unlike the
    rolling-window Whisper re-decode), so live partials arrive at the model's
    native chunk cadence (~560ms) for ~15% of one core. Provisioned by
    yumii.audio.nemotron_model (EN default; the 3.5 multilingual archive
    uses the same runtime with auto language detection).
    """

    _RATE = 16000

    def __init__(self, model_dir: str) -> None:
        import sherpa_onnx

        d = Path(model_dir)
        self._recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=str(d / "tokens.txt"),
            encoder=str(d / "encoder.int8.onnx"),
            decoder=str(d / "decoder.int8.onnx"),
            joiner=str(d / "joiner.int8.onnx"),
            num_threads=1,
            sample_rate=self._RATE,
            feature_dim=80,
            decoding_method="greedy_search",
        )
        self._stream = None
        self._last_partial = ""
        log.info("nemotron_stt_ready")

    def process_chunk(self, pcm16_bytes: bytes) -> dict | None:
        """Streaming interface: feed one frame; emit a partial whenever the
        recognizer's text changes (its internal 560ms chunks set the cadence)."""
        if self._stream is None:
            self._stream = self._recognizer.create_stream()
        samples = np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        self._stream.accept_waveform(self._RATE, samples)
        while self._recognizer.is_ready(self._stream):
            self._recognizer.decode_stream(self._stream)

        text = self._recognizer.get_result(self._stream).strip()
        if not text or text == self._last_partial:
            return None
        self._last_partial = text
        return {"type": "partial_transcript", "text": text}

    def transcribe(self, audio_data: np.ndarray) -> str | None:
        """Fallback for non-streaming usage: one shot through a fresh stream."""
        samples = audio_data.astype(np.float32) / 32768.0
        stream = self._recognizer.create_stream()
        stream.accept_waveform(self._RATE, samples)
        stream.input_finished()
        while self._recognizer.is_ready(stream):
            self._recognizer.decode_stream(stream)
        return self._recognizer.get_result(stream).strip() or None

    def reset(self) -> None:
        """Drop the current utterance without flushing it (mute, aborted capture)."""
        self._stream = None
        self._last_partial = ""

    def get_final(self) -> str | None:
        """End of turn: flush the stream tail, return the final text, and
        reset to a fresh stream for the next utterance."""
        text = ""
        if self._stream is not None:
            self._stream.input_finished()
            while self._recognizer.is_ready(self._stream):
                self._recognizer.decode_stream(self._stream)
            text = self._recognizer.get_result(self._stream).strip()
            self._stream = None
        self._last_partial = ""
        return text or None
