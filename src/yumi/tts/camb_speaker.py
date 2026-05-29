import base64
import aiohttp
import struct
from yumi.core.config import settings

class CambSpeaker:
    def __init__(self):
        self.api_key = settings.camb_api_key
        self.voice_id = settings.camb_voice_id

        if not self.api_key or not self.voice_id:
            raise ValueError(
                "\n\n  ❌  No CAMB.ai API Key or Voice ID configured.\n"
                "  Run 'yumi attune' or open ⚙️ Configure Senses and set them up.\n"
                "  Find your Voice ID at: https://client.camb.ai/\n"
            )

    async def stream_speak(self, text: str):
        """
        Async generator that yields raw PCM audio chunks.
        The first yield is metadata: {"type": "metadata", "sampleRate": int}.
        Subsequent yields are base64-encoded PCM audio chunks.
        """
        if not text:
            return

        # CAMB.ai free tier has a 500 character limit per request.
        # The LLM prompt is instructed to stay under 400, but we truncate just in case.
        if len(text) > 495:
            print(f"Warning: Text too long for CAMB.ai ({len(text)} chars), truncating.")
            text = text[:495] + "..."

        print("Synthesizing voice stream with CAMB.ai...")
        
        url = "https://client.camb.ai/apis/tts-stream"
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        
        # Ensure voice_id is an integer as required by CAMB.ai
        try:
            voice_id_int = int(self.voice_id)
        except ValueError:
            print(f"Error: CAMB.ai voice_id must be an integer, got: {self.voice_id}")
            return
            
        payload = {
            "text": text,
            "voice_id": voice_id_int,
            "language": "en-us",
            "speech_model": "mars-8.1-flash-beta",
            "output_configuration": {"format": "wav"},
        }
        
        timeout = aiohttp.ClientTimeout(total=120)
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        print(f"CAMB.ai API Error ({resp.status}): {error_text}")
                        resp.raise_for_status()
                    
                    is_first_chunk = True
                    buffer = b""
                    
                    async for chunk in resp.content.iter_chunked(4096):
                        if not chunk:
                            continue
                            
                        if is_first_chunk:
                            buffer += chunk
                            # Wait until we find the "data" chunk which marks the end of the header
                            data_idx = buffer.find(b"data")
                            if data_idx != -1 and len(buffer) >= data_idx + 8:
                                # Parse WAV header to get sample rate (always at byte 24)
                                sample_rate = struct.unpack("<I", buffer[24:28])[0]
                                
                                # Yield metadata first
                                yield {"type": "metadata", "sampleRate": sample_rate}
                                
                                # Strip the header up to data_idx + 8 and yield the rest of the buffer
                                audio_data = buffer[data_idx + 8:]
                                if audio_data:
                                    yield base64.b64encode(audio_data).decode("utf-8")
                                    
                                is_first_chunk = False
                                buffer = b""
                        else:
                            yield base64.b64encode(chunk).decode("utf-8")
                            
        except Exception as e:
            print(f"Error speaking response from CAMB.ai: {e}")
