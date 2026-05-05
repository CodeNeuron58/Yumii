import sounddevice as sd
import numpy as np
import webrtcvad
import collections
import wave
from faster_whisper import WhisperModel

# Configuration
RATE = 16000
FRAME_DURATION = 30  # ms
FRAME_SIZE = int(RATE * FRAME_DURATION / 1000)
CHANNELS = 1

def float_to_pcm16(audio):
    audio = np.clip(audio, -1, 1)
    audio_int16 = (audio * 32767).astype(np.int16)
    return audio_int16

def remove_silence(audio):
    vad = webrtcvad.Vad(3)
    frames = []
    num_frames = len(audio) // FRAME_SIZE

    for i in range(num_frames):
        frame = audio[i*FRAME_SIZE:(i+1)*FRAME_SIZE]
        if len(frame) < FRAME_SIZE:
            continue
        is_speech = vad.is_speech(frame.tobytes(), RATE)
        if is_speech:
            frames.append(frame)

    if len(frames) == 0:
        return audio
    return np.concatenate(frames)

def normalize_audio(audio):
    audio_float = audio.astype(np.float32)
    max_val = np.max(np.abs(audio_float))
    if max_val == 0:
        return audio
    # Normalize to -1 to 1, then scale to 90% of max int16 value
    audio_norm = (audio_float / max_val) * 0.9 * 32767.0
    return audio_norm.astype(np.int16)

class AudioPipeline:
    def __init__(self, model_size="base"):
        print(f"Loading Whisper model ({model_size})...")
        # CPU/INT8 as default to be compatible on any machine
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        self.vad = webrtcvad.Vad(3)  # Lowered aggressiveness to 1 so it doesn't miss speech
        print("Audio pipeline initialized.")

    def listen_and_capture(self):
        print("Listening...")
        import queue
        audio_queue = queue.Queue()

        def audio_callback(indata, frames, time, status):
            if status:
                print(status, flush=True)
            audio_queue.put(indata.copy())

        buffer = collections.deque(maxlen=15)
        recording = []
        triggered = False

        # Use InputStream for gapless continuous recording
        with sd.InputStream(samplerate=RATE, channels=CHANNELS, dtype='float32',
                            blocksize=FRAME_SIZE, callback=audio_callback):
            while True:
                # get audio chunk from the queue
                indata = audio_queue.get()
                audio = indata.flatten()
                pcm = float_to_pcm16(audio)
                
                # Make sure we only feed correct size frame to VAD
                if len(pcm) != FRAME_SIZE:
                    continue

                is_speech = self.vad.is_speech(pcm.tobytes(), RATE)

                if not triggered:
                    buffer.append((pcm, is_speech))
                    # Trigger if at least 6 out of recent 15 are speech
                    if sum([f[1] for f in buffer]) > 5:
                        triggered = True
                        print("Speech started")
                        recording.extend([f[0] for f in buffer])
                        buffer.clear()
                else:
                    recording.append(pcm)
                    buffer.append((pcm, is_speech))
                    # End if deeply silent (at least 12 out of 15 recent are silent)
                    if sum([not f[1] for f in buffer]) > 12:
                        print("Speech ended")
                        break

        if not recording:
            return np.array([], dtype=np.int16)
        return np.concatenate(recording)

    def process_audio(self, audio):
        audio = remove_silence(audio)
        audio = normalize_audio(audio)
        return audio

    def transcribe(self, audio_data):
        # faster-whisper expects float32 normalized between -1 and 1
        audio_float = audio_data.astype(np.float32) / 32768.0
        
        segments, _ = self.model.transcribe(audio_float, beam_size=5)
        text = "".join([segment.text for segment in segments])
        return text.strip()

    def run_cycle(self):
        raw_audio = self.listen_and_capture()
        if len(raw_audio) > 0:
            clean_audio = self.process_audio(raw_audio)
            
            if len(clean_audio) > 0:
                print("Transcribing... ")
                text = self.transcribe(clean_audio)
                print(f"Transcription: {text}")
                return text
        return ""
