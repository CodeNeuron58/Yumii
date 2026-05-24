import queue
import collections
import numpy as np
import sounddevice as sd
import torch
from faster_whisper import WhisperModel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RATE       = 16000
# Silero VAD requires EXACTLY 512 samples per chunk at 16 kHz (32 ms).
# Do NOT compute this from FRAME_DURATION — the math must land on 512.
FRAME_SIZE = 512
CHANNELS   = 1

# --- Thresholds (tune these if needed) ---
# How many of the last 15 frames must be speech to START recording
SPEECH_TRIGGER_FRAMES = 8      # was 6 (40%) — now 8 (53%). Harder to trigger.
# How many of the last 15 frames must be silent to STOP recording
SILENCE_END_FRAMES    = 12

# Minimum recorded audio duration to attempt transcription (seconds).
# Anything shorter is almost certainly a noise burst, not a real sentence.
MIN_SPEECH_DURATION_SEC = 0.7  # 700 ms

# Silero VAD confidence threshold — frames with probability below this are
# treated as non-speech. 0.5 is the default; raise to 0.6-0.7 for noisier
# environments.
SILERO_THRESHOLD = 0.5

# RMS energy gate — audio frames quieter than this are skipped before even
# going through VAD. This catches very-low-amplitude background noise.
# Range: 0.0–1.0 (float32 normalised). 0.01 ≈ barely audible.
RMS_ENERGY_GATE = 0.008

# Whisper no_speech_prob threshold — if Whisper itself thinks there was no
# real speech in the segment, we discard it instead of returning hallucinated
# text.
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


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

class AudioPipeline:
    """
    Voice-activity-detection + Whisper STT pipeline.

    Improvements over the original implementation:
      1. Silero VAD (neural) instead of WebRTC VAD (rule-based) →
         far fewer false triggers on keyboard clicks, fan noise, etc.
      2. RMS energy pre-gate → ultra-quiet frames are rejected before VAD.
      3. Minimum utterance duration gate → noise bursts < 700 ms are dropped.
      4. no_speech_prob filter → Whisper's own confidence score gates output,
         preventing hallucinated text on near-silent audio.
      5. Trigger threshold raised from 6/15 → 8/15 frames.
    """

    def __init__(self, model_size: str = "base"):
        # --- Whisper ---
        print(f"Loading Whisper model ({model_size})...")
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        print("Whisper model loaded.")

        # --- Silero VAD ---
        print("Loading Silero VAD...")
        # trust_repo=True suppresses the interactive "do you trust this repo?"
        # prompt that would block a non-interactive / first-run startup.
        # Silero VAD is a widely-used, well-audited library — safe to trust.
        self._silero_model, self._silero_utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=False,
            verbose=False,
            trust_repo=True,
        )
        # We only need the model itself for per-frame probability inference.
        # No VADIterator needed — we do our own trigger logic below.
        self._silero_model.reset_states()
        print("Silero VAD loaded. Audio pipeline ready.")

    # ------------------------------------------------------------------
    # Internal: per-frame Silero speech probability
    # ------------------------------------------------------------------

    def _is_speech_silero(self, audio_float32_frame: np.ndarray) -> bool:
        """
        Run one 512-sample (32 ms) float32 frame through Silero.

        Silero requires EXACTLY 512 samples at 16 kHz — feeding fewer
        samples raises "Input audio chunk is too short".
        Returns True if speech probability >= SILERO_THRESHOLD.
        """
        # Model expects a 1-D float32 tensor: shape [512]
        tensor = torch.FloatTensor(audio_float32_frame)
        with torch.no_grad():
            prob = self._silero_model(tensor, RATE).item()
        return prob >= SILERO_THRESHOLD

    def _reset_vad(self):
        """Reset Silero's internal hidden state between utterances."""
        self._silero_model.reset_states()

    # ------------------------------------------------------------------
    # Capture
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
                indata = audio_q.get()
                audio_f32 = indata.flatten()          # float32, -1..1

                # ── Gate 1: RMS energy (pre-trigger only) ─────────────────
                # Skip near-silent frames ONLY before speech has started.
                # Once triggered, we record EVERYTHING — dropping quiet frames
                # during speech creates holes in the audio that break Whisper.
                if not triggered and rms_energy(audio_f32) < RMS_ENERGY_GATE:
                    pre_buffer.append((float_to_pcm16(audio_f32), False))
                    continue

                # ── Gate 2: Silero VAD ──────────────────────────────────
                is_speech = self._is_speech_silero(audio_f32)
                pcm16 = float_to_pcm16(audio_f32)

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
    # Transcribe
    # ------------------------------------------------------------------

    def transcribe(self, audio_data: np.ndarray) -> str:
        """
        Run faster-whisper on int16 PCM audio.

        Returns the transcribed string, or an empty string if:
          - The audio is too short (< MIN_SPEECH_DURATION_SEC).
          - Whisper's no_speech_prob is too high (hallucination guard).
        """
        # ── Gate 3: Minimum duration ────────────────────────────────────
        duration_sec = len(audio_data) / RATE
        if duration_sec < MIN_SPEECH_DURATION_SEC:
            print(f"⚠  Audio too short ({duration_sec:.2f}s < {MIN_SPEECH_DURATION_SEC}s), skipping.")
            return ""

        # faster-whisper expects float32 in [-1, 1]
        audio_float = audio_data.astype(np.float32) / 32768.0

        segments, info = self.model.transcribe(
            audio_float,
            # beam_size=1 (greedy) is 3-5x faster than beam_size=5 on CPU
            # with negligible accuracy loss for clean speech. Latency matters.
            beam_size=1,
            condition_on_previous_text=False,
            suppress_blank=True,
            no_speech_threshold=NO_SPEECH_PROB_THRESHOLD,
        )

        # ── Gate 4: no_speech_prob per segment ─────────────────────────
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
