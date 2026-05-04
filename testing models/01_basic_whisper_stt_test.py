"""
Simple Whisper STT Test

Basic end-to-end test of OpenAI Whisper for speech recognition.
- Records audio from microphone
- Saves to WAV file
- Transcribes using Whisper "tiny" model

This was the first STT prototype before moving to faster-whisper
for better performance and WebRTC VAD integration.

Dependencies:
    pip install openai-whisper sounddevice scipy

Note: Requires ffmpeg installed on system for Whisper
"""

import sounddevice as sd
from scipy.io.wavfile import write
import whisper

# Configuration
DURATION = 5       # seconds to record
SAMPLERATE = 16000  # 16kHz is good for speech recognition

print("Recording... Speak now")

# Record audio from microphone
audio = sd.rec(int(DURATION * SAMPLERATE), samplerate=SAMPLERATE, channels=1)
sd.wait()  # Wait for recording to complete

# Save to WAV file
write("speech.wav", SAMPLERATE, audio)
print(f"Saved to speech.wav ({DURATION}s)")

# Load Whisper model and transcribe
print("Loading Whisper model...")
model = whisper.load_model("tiny")  # tiny = fastest, base = better accuracy

print("Transcribing...")
result = model.transcribe("speech.wav")

print(f"You said: {result['text']}")