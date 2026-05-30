import io
import queue
import asyncio
from typing import Callable
import wave
import collections
import numpy as np
import torch
from yumi.audio.stt_factory import get_stt_provider
from yumi.core.interfaces import BaseSTTProvider

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RATE       = 16000
FRAME_SIZE = 512
CHANNELS   = 1

SPEECH_TRIGGER_FRAMES    = 8
SILENCE_END_FRAMES       = 12
MIN_SPEECH_DURATION_SEC  = 0.7
SILERO_THRESHOLD         = 0.5
RMS_ENERGY_GATE          = 0.008
NO_SPEECH_PROB_THRESHOLD = 0.45

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def float_to_pcm16(audio: np.ndarray) -> np.ndarray:
    audio = np.clip(audio, -1, 1)
    return (audio * 32767).astype(np.int16)

def normalize_audio(audio: np.ndarray) -> np.ndarray:
    audio_float = audio.astype(np.float32)
    max_val = np.max(np.abs(audio_float))
    if max_val == 0:
        return audio
    return ((audio_float / max_val) * 0.9 * 32767.0).astype(np.int16)

def rms_energy(audio_float32: np.ndarray) -> float:
    return float(np.sqrt(np.mean(audio_float32 ** 2)))

def _pcm16_to_wav_bytes(audio_int16: np.ndarray, sample_rate: int = RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())
    return buf.getvalue()

# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

class AudioPipeline:
    """
    Voice-activity-detection + Transcription pipeline.
    Uses Silero VAD for speech detection and a pluggable BaseSTTProvider for transcription.
    """
    def __init__(self, provider: str = "local", model_size: str = "base", groq_api_key: str | None = None):
        # VAD is always loaded locally
        print("Loading Silero VAD...")
        self._silero_model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=False,
            verbose=False,
            trust_repo=True,
        )
        self._silero_model.reset_states()
        print("Silero VAD loaded.")

        # Transcription provider is pluggable
        self.transcriber = get_stt_provider()
        print("Audio pipeline ready.")

    def _is_speech_silero(self, audio_float32_frame: np.ndarray) -> bool:
        tensor = torch.FloatTensor(audio_float32_frame)
        with torch.no_grad():
            prob = self._silero_model(tensor, RATE).item()
        return prob >= SILERO_THRESHOLD

    def _reset_vad(self) -> None:
        self._silero_model.reset_states()

    async def stream_capture(self, queue: asyncio.Queue, on_speech_start: Callable[[], None] | None = None) -> np.ndarray:
        self._reset_vad()
        recording = []
        pre_buffer: collections.deque = collections.deque(maxlen=15)
        triggered = False
        accumulation_buffer = np.array([], dtype=np.float32)

        while True:
            chunk_bytes = await queue.get()
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
                    if speech_count >= SPEECH_TRIGGER_FRAMES:
                        triggered = True
                        print("🎙  Speech started (stream)")
                        if on_speech_start:
                            on_speech_start()
                        recording.extend(frame for frame, _ in pre_buffer)
                        pre_buffer.clear()
                else:
                    recording.append(pcm16)
                    pre_buffer.append((pcm16, is_speech))
                    silence_count = sum(1 for _, s in pre_buffer if not s)
                    if silence_count >= SILENCE_END_FRAMES:
                        print("🔇  Speech ended (stream)")
                        return np.concatenate(recording) if recording else np.array([], dtype=np.int16)

        return np.array([], dtype=np.int16)

    def process_audio(self, audio: np.ndarray) -> np.ndarray:
        return normalize_audio(audio)

    def transcribe(self, audio_data: np.ndarray) -> str:
        duration_sec = len(audio_data) / RATE
        if duration_sec < MIN_SPEECH_DURATION_SEC:
            print(f"⚠  Audio too short ({duration_sec:.2f}s < {MIN_SPEECH_DURATION_SEC}s), skipping.")
            return ""

        text = self.transcriber.transcribe(audio_data)
        return text.strip() if text else ""

    def run_cycle(self, on_speech_start: Callable[[], None] | None = None) -> str:
        raw_audio = self.listen_and_capture(on_speech_start=on_speech_start)
        if len(raw_audio) == 0:
            return ""
        clean_audio = self.process_audio(raw_audio)
        if len(clean_audio) == 0:
            return ""
        text = self.transcribe(clean_audio)
        return text
