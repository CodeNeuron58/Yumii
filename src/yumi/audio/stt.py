import io
import queue
import wave
import collections
import numpy as np
import sounddevice as sd
import torch

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RATE       = 16000
# Silero VAD requires EXACTLY 512 samples per chunk at 16 kHz (32 ms).
FRAME_SIZE = 512
CHANNELS   = 1

# --- Thresholds (tune these if needed) ---
SPEECH_TRIGGER_FRAMES    = 8    # of last 15 frames must be speech to START
SILENCE_END_FRAMES       = 12   # of last 15 frames must be silent to STOP
MIN_SPEECH_DURATION_SEC  = 0.7  # anything < 700 ms is likely noise
SILERO_THRESHOLD         = 0.5  # Silero speech-probability cutoff
RMS_ENERGY_GATE          = 0.008
NO_SPEECH_PROB_THRESHOLD = 0.45


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def float_to_pcm16(audio: np.ndarray) -> np.ndarray:
    """Convert float32 audio (-1..1) to int16 PCM."""
    audio = np.clip(audio, -1, 1)
    return (audio * 32767).astype(np.int16)


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    """Normalize int16 audio to 90 % of max amplitude."""
    audio_float = audio.astype(np.float32)
    max_val = np.max(np.abs(audio_float))
    if max_val == 0:
        return audio
    return ((audio_float / max_val) * 0.9 * 32767.0).astype(np.int16)


def rms_energy(audio_float32: np.ndarray) -> float:
    """Root-mean-square energy of a float32 audio frame."""
    return float(np.sqrt(np.mean(audio_float32 ** 2)))


def _pcm16_to_wav_bytes(audio_int16: np.ndarray, sample_rate: int = RATE) -> bytes:
    """Encode a int16 numpy array as an in-memory WAV file and return raw bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)          # int16 = 2 bytes per sample
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

class AudioPipeline:
    """
    Voice-activity-detection + Whisper STT pipeline.

    Supports two transcription backends:
      - "local"  : faster-whisper running on CPU (private, no API key needed)
      - "groq"   : Groq Whisper API (cloud, ~5-10x faster, requires GROQ_API_KEY)

    Silero VAD is used for speech detection in BOTH modes — the only difference
    is what happens after the audio is captured.

    Noise-rejection stack (shared by both backends):
      1. RMS energy pre-gate (pre-trigger only) → blocks fan/AC hum
      2. Silero VAD per-frame probability       → neural speech detection
      3. Minimum utterance duration gate        → drops bursts < 700 ms
      4. no_speech_prob filter (local only)     → Whisper hallucination guard
    """

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def __init__(
        self,
        provider: str = "local",
        model_size: str = "base",
        groq_api_key: str | None = None,
    ):
        self.provider = provider.lower()

        # Silero VAD is always loaded — it drives speech detection for both modes.
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

        if self.provider == "groq":
            self._init_groq(groq_api_key)
        else:
            self._init_local_whisper(model_size)

        print("Audio pipeline ready.")

    def _init_local_whisper(self, model_size: str) -> None:
        from faster_whisper import WhisperModel
        print(f"Loading Whisper model ({model_size}) on CPU...")
        self._whisper = WhisperModel(model_size, device="cpu", compute_type="int8")
        print(f"Whisper model ({model_size}) loaded.")

    def _init_groq(self, api_key: str | None) -> None:
        from groq import Groq
        if not api_key:
            raise ValueError(
                "\n\n  ❌  No Groq API key configured for Groq STT.\n"
                "  Run 'yumi attune' or open ⚙️ Configure Senses → Listening Settings.\n"
            )
        self._groq_client = Groq(api_key=api_key)
        print("Groq Whisper STT ready (whisper-large-v3-turbo).")

    # ------------------------------------------------------------------
    # Silero VAD helpers
    # ------------------------------------------------------------------

    def _is_speech_silero(self, audio_float32_frame: np.ndarray) -> bool:
        """
        Run one 512-sample (32 ms) float32 frame through Silero.
        Returns True if speech probability >= SILERO_THRESHOLD.
        """
        tensor = torch.FloatTensor(audio_float32_frame)
        with torch.no_grad():
            prob = self._silero_model(tensor, RATE).item()
        return prob >= SILERO_THRESHOLD

    def _reset_vad(self) -> None:
        """Reset Silero's internal hidden state between utterances."""
        self._silero_model.reset_states()

    # ------------------------------------------------------------------
    # Capture (shared by both backends)
    # ------------------------------------------------------------------

    def listen_and_capture(self) -> np.ndarray:
        """
        Block until a complete utterance is captured.
        Returns int16 PCM numpy array, or an empty array if nothing was heard.
        """
        print("Listening...")
        self._reset_vad()

        audio_q: queue.Queue = queue.Queue()

        def _callback(indata, frames, time_info, status):
            if status:
                print(f"[Audio status] {status}", flush=True)
            audio_q.put(indata.copy())

        # Rolling pre-speech buffer so we don't clip the start of a sentence
        pre_buffer: collections.deque = collections.deque(maxlen=15)
        recording = []
        triggered = False

        with sd.InputStream(
            samplerate=RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=FRAME_SIZE,
            callback=_callback,
        ):
            while True:
                indata   = audio_q.get()
                audio_f32 = indata.flatten()

                # ── Gate 1: RMS energy (pre-trigger only) ──────────────
                # Skip near-silent frames ONLY before speech has started.
                # Once triggered we record EVERYTHING — dropping quiet frames
                # during speech creates holes that break transcription.
                if not triggered and rms_energy(audio_f32) < RMS_ENERGY_GATE:
                    pre_buffer.append((float_to_pcm16(audio_f32), False))
                    continue

                # ── Gate 2: Silero VAD ──────────────────────────────────
                is_speech = self._is_speech_silero(audio_f32)
                pcm16     = float_to_pcm16(audio_f32)

                if not triggered:
                    pre_buffer.append((pcm16, is_speech))
                    speech_count = sum(1 for _, s in pre_buffer if s)
                    if speech_count >= SPEECH_TRIGGER_FRAMES:
                        triggered = True
                        print("🎙  Speech started")
                        recording.extend(frame for frame, _ in pre_buffer)
                        pre_buffer.clear()
                else:
                    recording.append(pcm16)
                    pre_buffer.append((pcm16, is_speech))
                    silence_count = sum(1 for _, s in pre_buffer if not s)
                    if silence_count >= SILENCE_END_FRAMES:
                        print("🔇  Speech ended")
                        break

        if not recording:
            return np.array([], dtype=np.int16)
        return np.concatenate(recording)

    # ------------------------------------------------------------------
    # Post-process
    # ------------------------------------------------------------------

    def process_audio(self, audio: np.ndarray) -> np.ndarray:
        """Normalize captured int16 audio."""
        return normalize_audio(audio)

    # ------------------------------------------------------------------
    # Transcription — dispatches to the correct backend
    # ------------------------------------------------------------------

    def transcribe(self, audio_data: np.ndarray) -> str:
        """
        Transcribe int16 PCM audio.

        Returns the transcribed string, or an empty string if:
          - The audio is too short (< MIN_SPEECH_DURATION_SEC).
          - Whisper's no_speech_prob is too high (local mode only).
          - An API error occurs (Groq mode).
        """
        # ── Gate 3: Minimum duration (both backends) ────────────────────
        duration_sec = len(audio_data) / RATE
        if duration_sec < MIN_SPEECH_DURATION_SEC:
            print(f"⚠  Audio too short ({duration_sec:.2f}s < {MIN_SPEECH_DURATION_SEC}s), skipping.")
            return ""

        if self.provider == "groq":
            return self._transcribe_groq(audio_data)
        else:
            return self._transcribe_local(audio_data)

    def _transcribe_local(self, audio_data: np.ndarray) -> str:
        """Transcribe using faster-whisper on CPU (private, offline)."""
        # faster-whisper expects float32 in [-1, 1]
        audio_float = audio_data.astype(np.float32) / 32768.0

        segments, _ = self._whisper.transcribe(
            audio_float,
            # beam_size=1 (greedy) is 3-5x faster than beam_size=5 on CPU
            # with negligible accuracy loss for clean speech. Latency matters.
            beam_size=1,
            condition_on_previous_text=False,
            suppress_blank=True,
            no_speech_threshold=NO_SPEECH_PROB_THRESHOLD,
        )

        # ── Gate 4: no_speech_prob per segment (local only) ────────────
        text_parts = []
        for segment in segments:
            if segment.no_speech_prob > NO_SPEECH_PROB_THRESHOLD:
                print(
                    f"⚠  Segment discarded (no_speech_prob={segment.no_speech_prob:.2f}): "
                    f'"{segment.text.strip()}"'
                )
                continue
            text_parts.append(segment.text)

        return "".join(text_parts).strip()

    def _transcribe_groq(self, audio_data: np.ndarray) -> str:
        """
        Transcribe by sending the captured WAV buffer to Groq's Whisper API.

        Groq runs whisper-large-v3-turbo on LPU hardware — typical response
        time is 100-300ms for a 5-second sentence (vs 1-2s locally on CPU).
        """
        try:
            wav_bytes = _pcm16_to_wav_bytes(audio_data)
            result = self._groq_client.audio.transcriptions.create(
                file=("audio.wav", wav_bytes),
                model="whisper-large-v3-turbo",
                response_format="text",
                language="en",
            )
            return result.strip() if result else ""
        except Exception as e:
            print(f"❌  Groq STT error: {e}")
            return ""

    # ------------------------------------------------------------------
    # Full cycle
    # ------------------------------------------------------------------

    def run_cycle(self) -> str:
        """Capture one utterance and return its transcription."""
        raw_audio = self.listen_and_capture()
        if len(raw_audio) == 0:
            return ""

        clean_audio = self.process_audio(raw_audio)
        if len(clean_audio) == 0:
            return ""

        print("Transcribing...")
        text = self.transcribe(clean_audio)
        if text:
            print(f"✅ Transcription: {text}")
        else:
            print("🔇 No speech detected (filtered).")
        return text
