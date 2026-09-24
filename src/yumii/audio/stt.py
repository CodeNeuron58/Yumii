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
# With Smart Turn available, a shorter silence is enough to *ask* the model
# whether the user finished; the fixed tail is only the fallback path.
SILENCE_END_FRAMES_QUICK = 6
SMART_TURN_RECHECK_STRIDE = 6
_SMART_TURN_MAX_RECHECKS = 5
MIN_SPEECH_DURATION_SEC = 0.7
# Hard bound on one utterance: audio that never dips below the VAD threshold
# (music/TV near the mic) must eventually finalize instead of growing forever.
_MAX_UTTERANCE_SEC = 60
_MAX_UTTERANCE_FRAMES = int(_MAX_UTTERANCE_SEC * RATE / FRAME_SIZE)
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

        # Smart Turn (optional): decides "paused mid-thought" vs "finished
        # speaking" from prosody. Unavailable model -> legacy fixed tail.
        from yumii.audio.smart_turn import get_smart_turn

        self._smart_turn = get_smart_turn()

        self.transcriber = get_stt_provider()
        log.info("audio_pipeline_ready", smart_turn=self._smart_turn is not None)

    def set_speaking_gate(self, armed: bool) -> None:
        """Swap between normal listening and barge-in gating (called mid-capture)."""
        if armed:
            self.speech_trigger_frames = BARGE_IN_TRIGGER_FRAMES
            self.speech_threshold = SILERO_BARGE_THRESHOLD
        else:
            self.speech_trigger_frames = SPEECH_TRIGGER_FRAMES
            self.speech_threshold = SILERO_THRESHOLD

    async def _check_turn_end(
        self, recording: list, consecutive_silence: int, rechecks: int
    ) -> tuple[bool, int]:
        """Decide whether the user's turn is over. Returns (should_end, new_rechecks).

        ``consecutive_silence`` counts silent frames since the last speech
        frame — absolute, not the 15-frame pre_buffer window, so recheck
        thresholds can keep climbing. With Smart Turn: ~190ms of silence is
        enough to ask the model; "incomplete" keeps listening, re-asking
        every ~190ms of extra silence, force-closing after the cap (user
        walked away mid-sentence). Without it: the legacy 12-frame (~384ms)
        silent tail.
        """
        if self._smart_turn is None:
            return consecutive_silence >= SILENCE_END_FRAMES, rechecks

        if consecutive_silence < (
            SILENCE_END_FRAMES_QUICK + rechecks * SMART_TURN_RECHECK_STRIDE
        ):
            return False, rechecks

        if recording:
            audio = np.concatenate(recording).astype(np.float32) / 32768.0
        else:
            audio = np.zeros(FRAME_SIZE, dtype=np.float32)
        complete, prob = await asyncio.to_thread(self._smart_turn.is_complete, audio)

        if complete:
            log.debug("smart_turn_complete", prob=round(prob, 3), silence_frames=consecutive_silence)
            return True, rechecks
        if rechecks >= _SMART_TURN_MAX_RECHECKS:
            log.debug("smart_turn_forced_end", rechecks=rechecks)
            return True, rechecks
        log.debug("smart_turn_incomplete", prob=round(prob, 3), rechecks=rechecks + 1)
        return False, rechecks + 1

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
        rechecks = 0
        utterance_frames = 0
        consecutive_silence = 0
        accumulation_buffer = np.array([], dtype=np.float32)

        while True:
            chunk_bytes = await queue.get()
            if chunk_bytes is None:  # mute sentinel
                self._reset_vad()
                recording = []
                # Keep pre-buffered speech onset: the playback-end sentinel
                # arrives ~400ms after her audio stops, and a user replying
                # inside that window must not lose their first phonemes.
                if not any(s for _, s in list(pre_buffer)[-6:]):
                    pre_buffer.clear()
                triggered = False
                rechecks = 0
                utterance_frames = 0
                consecutive_silence = 0
                accumulation_buffer = np.array([], dtype=np.float32)
                log.debug("capture_reset_by_mute")
                continue
            if len(chunk_bytes) % 2 != 0:
                # np.frombuffer would raise on odd byte counts — and a dead
                # capture used to lose its recording AND prime stale Vosk
                # state for the next utterance.
                log.warning("odd_frame_dropped", bytes=len(chunk_bytes))
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
                    utterance_frames += 1
                    if is_speech:
                        consecutive_silence = 0
                        # The climbing recheck stride only survives within one
                        # continuous pause — speech must reset it, or pauses
                        # from earlier in the turn force-cut later ones.
                        rechecks = 0
                    else:
                        consecutive_silence += 1

                    if utterance_frames >= _MAX_UTTERANCE_FRAMES:
                        log.info("utterance_force_capped", seconds=_MAX_UTTERANCE_SEC)
                        should_end = True
                    else:
                        should_end, rechecks = await self._check_turn_end(
                            recording, consecutive_silence, rechecks
                        )
                    if should_end:
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
        # Discard residue from an aborted capture: without this, a dead
        # capture's half-utterance is prepended to the next transcript.
        if hasattr(self.transcriber, "get_final"):
            self.transcriber.get_final()
        pre_buffer: collections.deque = collections.deque(maxlen=15)
        triggered = False
        rechecks = 0
        recording: list[np.ndarray] = []
        utterance_frames = 0
        consecutive_silence = 0
        accumulation_buffer = np.array([], dtype=np.float32)

        while True:
            chunk_bytes = await queue.get()
            if chunk_bytes is None:  # mute sentinel
                self._reset_vad()
                # Keep pre-buffered speech onset (see stream_capture).
                if not any(s for _, s in list(pre_buffer)[-6:]):
                    pre_buffer.clear()
                triggered = False
                rechecks = 0
                recording = []
                utterance_frames = 0
                consecutive_silence = 0
                accumulation_buffer = np.array([], dtype=np.float32)
                if hasattr(self.transcriber, "get_final"):
                    self.transcriber.get_final()  # discard the half-utterance
                log.debug("capture_reset_by_mute")
                continue
            if len(chunk_bytes) % 2 != 0:
                log.warning("odd_frame_dropped", bytes=len(chunk_bytes))
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
                    recording.append(pcm16)
                    utterance_frames += 1
                    if is_speech:
                        consecutive_silence = 0
                        rechecks = 0  # speech resets the climbing recheck stride
                    else:
                        consecutive_silence += 1
                    if hasattr(self.transcriber, "process_chunk"):
                        event = await asyncio.to_thread(self.transcriber.process_chunk, pcm16.tobytes())
                        if event and event.get("type") == "partial_transcript" and on_partial:
                            log.info("partial_transcript_generated", text=event["text"])
                            import inspect
                            if inspect.iscoroutinefunction(on_partial):
                                await on_partial(event["text"])
                            else:
                                on_partial(event["text"])

                    if utterance_frames >= _MAX_UTTERANCE_FRAMES:
                        log.info("utterance_force_capped", seconds=_MAX_UTTERANCE_SEC)
                        should_end = True
                    else:
                        should_end, rechecks = await self._check_turn_end(
                            recording, consecutive_silence, rechecks
                        )
                    if should_end:
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
