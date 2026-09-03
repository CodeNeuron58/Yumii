"""VAD + STT pipeline: capture audio, detect speech boundaries, transcribe utterances."""


import asyncio
import collections
from typing import Any, Callable

import numpy as np

from yumii.audio.silero_vad import SileroVAD
from yumii.audio.stt_factory import get_stt_provider

from yumii.core.logging import get_logger

log = get_logger(__name__)

RATE = 16000
FRAME_SIZE = 512
CHANNELS = 1

SPEECH_TRIGGER_FRAMES = 8
SILENCE_END_FRAMES = 12
MIN_SPEECH_DURATION_SEC = 0.7
SILERO_THRESHOLD = 0.5
# Energy floor before running the VAD — skips faint noise; humming is handled by the Groq confidence gate.
RMS_ENERGY_GATE = 0.012
NO_SPEECH_PROB_THRESHOLD = 0.45

# Barge-in gate, armed while Yumii is speaking: her own voice leaks through
# echo cancellation, so interrupting her requires longer sustained speech at a
# higher confidence than an ordinary turn start. ~15 frames x 32ms = ~480ms.
BARGE_IN_TRIGGER_FRAMES = 15
SILERO_BARGE_THRESHOLD = 0.6


def float_to_pcm16(audio: np.ndarray) -> np.ndarray:
    """Convert float32 audio data to PCM int16 format."""
    audio = np.clip(audio, -1, 1)
    return (audio * 32767).astype(np.int16)


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    """Normalize audio amplitude to a safe peak value."""
    audio_float = audio.astype(np.float32)
    max_val = np.max(np.abs(audio_float))
    if max_val == 0:
        return audio
    return ((audio_float / max_val) * 0.9 * 32767.0).astype(np.int16)


def rms_energy(audio_float32: np.ndarray) -> float:
    """Calculate the Root Mean Square (RMS) energy of an audio frame."""
    return float(np.sqrt(np.mean(audio_float32**2)))


class AudioPipeline:
    """VAD (Silero) + pluggable STT transcription pipeline."""

    def __init__(
        self,
        provider: str = "local",
        model_size: str = "base",
        groq_api_key: str | None = None,
    ) -> None:
        """Initialize the audio pipeline, loading VAD and STT models."""
        # VAD is always local — bundled ONNX, no torch, no download.
        log.info("silero_vad_loading")
        self._silero_model = SileroVAD()

        # Speech-gate parameters, adjusted live by the engine: normal values
        # while listening, stricter barge-in values while she is speaking.
        self.speech_trigger_frames = SPEECH_TRIGGER_FRAMES
        self.speech_threshold = SILERO_THRESHOLD

        self.transcriber = get_stt_provider()
        log.info("audio_pipeline_ready")

    def set_speaking_gate(self, armed: bool) -> None:
        """Swap between normal listening and barge-in gating (called mid-capture)."""
        if armed:
            self.speech_trigger_frames = BARGE_IN_TRIGGER_FRAMES
            self.speech_threshold = SILERO_BARGE_THRESHOLD
        else:
            self.speech_trigger_frames = SPEECH_TRIGGER_FRAMES
            self.speech_threshold = SILERO_THRESHOLD

    def _is_speech_silero(self, audio_float32_frame: np.ndarray) -> bool:
        prob = self._silero_model(audio_float32_frame, RATE)
        return prob >= self.speech_threshold

    def _reset_vad(self) -> None:
        self._silero_model.reset_states()

    async def stream_capture(
        self, queue: asyncio.Queue, on_speech_start: Callable[[], None] | None = None
    ) -> np.ndarray:
        """Consume audio until a speech segment completes; a None chunk is the mute sentinel (resets capture)."""
        self._reset_vad()
        recording = []
        pre_buffer: collections.deque = collections.deque(maxlen=15)
        triggered = False
        accumulation_buffer = np.array([], dtype=np.float32)

        while True:
            chunk_bytes = await queue.get()
            if chunk_bytes is None:  # mute sentinel
                self._reset_vad()
                recording = []
                pre_buffer.clear()
                triggered = False
                accumulation_buffer = np.array([], dtype=np.float32)
                log.debug("capture_reset_by_mute")
                continue
            audio_int16 = np.frombuffer(chunk_bytes, dtype=np.int16)
            audio_f32 = audio_int16.astype(np.float32) / 32768.0
            accumulation_buffer = np.append(accumulation_buffer, audio_f32)

            while len(accumulation_buffer) >= FRAME_SIZE:
                frame = accumulation_buffer[:FRAME_SIZE]
                accumulation_buffer = accumulation_buffer[FRAME_SIZE:]

                if not triggered and rms_energy(frame) < RMS_ENERGY_GATE:
                    pre_buffer.append((float_to_pcm16(frame), False))
                    continue

                is_speech = self._is_speech_silero(frame)
                pcm16 = float_to_pcm16(frame)

                if not triggered:
                    pre_buffer.append((pcm16, is_speech))
                    speech_count = sum(1 for _, s in pre_buffer if s)
                    if speech_count >= self.speech_trigger_frames:
                        triggered = True
                        log.debug("speech_started")
                        if on_speech_start:
                            on_speech_start()
                        recording.extend(frame for frame, _ in pre_buffer)
                        pre_buffer.clear()
                else:
                    recording.append(pcm16)
                    pre_buffer.append((pcm16, is_speech))
                    silence_count = sum(1 for _, s in pre_buffer if not s)
                    if silence_count >= SILENCE_END_FRAMES:
                        log.debug("speech_ended")
                        return (
                            np.concatenate(recording)
                            if recording
                            else np.array([], dtype=np.int16)
                        )

        return np.array([], dtype=np.int16)

    async def stream_capture_and_transcribe(
        self,
        queue: asyncio.Queue,
        on_speech_start: Callable[[], None] | None = None,
        on_partial: Callable[[str], Any] | None = None
    ) -> str | None:
        """Like stream_capture but streams chunks to a partial-capable transcriber (None = mute sentinel)."""
        self._reset_vad()
        pre_buffer: collections.deque = collections.deque(maxlen=15)
        triggered = False
        accumulation_buffer = np.array([], dtype=np.float32)

        while True:
            chunk_bytes = await queue.get()
            if chunk_bytes is None:  # mute sentinel
                self._reset_vad()
                pre_buffer.clear()
                triggered = False
                accumulation_buffer = np.array([], dtype=np.float32)
                if hasattr(self.transcriber, "get_final"):
                    self.transcriber.get_final()  # discard the half-utterance
                log.debug("capture_reset_by_mute")
                continue
            audio_int16 = np.frombuffer(chunk_bytes, dtype=np.int16)
            audio_f32 = audio_int16.astype(np.float32) / 32768.0
            accumulation_buffer = np.append(accumulation_buffer, audio_f32)

            while len(accumulation_buffer) >= FRAME_SIZE:
                frame = accumulation_buffer[:FRAME_SIZE]
                accumulation_buffer = accumulation_buffer[FRAME_SIZE:]

                if not triggered and rms_energy(frame) < RMS_ENERGY_GATE:
                    pre_buffer.append((float_to_pcm16(frame), False))
                    continue

                is_speech = self._is_speech_silero(frame)
                pcm16 = float_to_pcm16(frame)

                if not triggered:
                    pre_buffer.append((pcm16, is_speech))
                    speech_count = sum(1 for _, s in pre_buffer if s)
                    if speech_count >= self.speech_trigger_frames:
                        triggered = True
                        log.debug("speech_started")
                        if on_speech_start:
                            on_speech_start()

                        if hasattr(self.transcriber, "process_chunk"):
                            for f, _ in pre_buffer:
                                event = await asyncio.to_thread(self.transcriber.process_chunk, f.tobytes())
                                if event and event.get("type") == "partial_transcript" and on_partial:
                                    log.info("partial_transcript_generated", text=event["text"])
                                    import inspect
                                    if inspect.iscoroutinefunction(on_partial):
                                        await on_partial(event["text"])
                                    else:
                                        on_partial(event["text"])
                        pre_buffer.clear()
                else:
                    if hasattr(self.transcriber, "process_chunk"):
                        event = await asyncio.to_thread(self.transcriber.process_chunk, pcm16.tobytes())
                        if event and event.get("type") == "partial_transcript" and on_partial:
                            log.info("partial_transcript_generated", text=event["text"])
                            import inspect
                            if inspect.iscoroutinefunction(on_partial):
                                await on_partial(event["text"])
                            else:
                                on_partial(event["text"])

                    pre_buffer.append((pcm16, is_speech))
                    silence_count = sum(1 for _, s in pre_buffer if not s)
                    if silence_count >= SILENCE_END_FRAMES:
                        log.debug("speech_ended")
                        if hasattr(self.transcriber, "get_final"):
                            return self.transcriber.get_final()
                        return None

        return None

    def process_audio(self, audio: np.ndarray) -> np.ndarray:
        """Apply post-capture processing (normalization) to the audio array."""
        return normalize_audio(audio)

    def transcribe(self, audio_data: np.ndarray) -> str:
        """Convert a complete audio utterance into text."""
        duration_sec = len(audio_data) / RATE
        if duration_sec < MIN_SPEECH_DURATION_SEC:
            log.debug("audio_too_short", duration_sec=round(duration_sec, 2), minimum_sec=MIN_SPEECH_DURATION_SEC)
            return ""

        text = self.transcriber.transcribe(audio_data)
        return text.strip() if text else ""
