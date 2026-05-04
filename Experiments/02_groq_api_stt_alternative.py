"""
Alternative Audio Pipeline using Groq API for STT

This module implements an audio capture and transcription pipeline
using Groq's hosted Whisper API instead of local faster-whisper.

Pros of Groq approach:
- No local model download (~150MB for whisper-base)
- Potentially faster on slow CPUs
- Always latest model version

Cons of Groq approach:
- Requires internet connection
- API latency variability
- API costs at scale
- Audio must be sent over network

This was tested but local faster-whisper was selected for production
to ensure offline capability and zero API costs.

Usage:
    from pipeline import AudioPipeline
    pipeline = AudioPipeline()
    text = pipeline.run_cycle()  # Returns transcribed text
"""

import sounddevice as sd
import numpy as np
import webrtcvad
import collections
import wave
import io
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

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
    """
    Audio capture and transcription pipeline using Groq API.
    
    This class handles:
    - Continuous microphone listening
    - Voice Activity Detection (VAD)
    - Speech segmentation (start/end detection)
    - Audio preprocessing (silence removal, normalization)
    - Transcription via Groq Whisper API
    
    Attributes:
        client: Groq API client instance
        vad: WebRTC Voice Activity Detector
    """
    
    def __init__(self):
        """Initialize the audio pipeline with Groq client."""
        print("Initializing Groq API client...")
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.vad = webrtcvad.Vad(3)  # Aggressiveness: 0 (low) to 3 (high)
        print("Audio pipeline initialized.")

    def listen_and_capture(self):
        """
        Listen for speech using VAD and capture audio.
        
        Uses a ring buffer (15 frames) to detect speech start/end:
        - Speech start: 6/15 frames contain speech
        - Speech end: 12/15 frames are silent
        
        Returns:
            numpy array of captured audio (int16)
        """
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
        # Convert PCM16 numpy array to WAV bytes
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav_file:
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(2) # 16-bit PCM
            wav_file.setframerate(RATE)
            wav_file.writeframes(audio_data.tobytes())
        buffer.seek(0)
        buffer.name = "audio.wav"

        # Send to Groq API
        try:
            translation = self.client.audio.transcriptions.create(
                file=(buffer.name, buffer.read()),
                model="whisper-large-v3",
                temperature=0.0, # 0.0 reduces hallucinations
                condition_on_previous_text=False # prevents hallucination loops
            )
            return translation.text.strip()
        except Exception as e:
            print(f"Transcription error: {e}")
            return ""

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
