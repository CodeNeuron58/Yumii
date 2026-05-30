import base64
import aiohttp
import struct
from yumi.core.config import settings
from yumi.core.interfaces import BaseSpeaker
from typing import AsyncGenerator, Any

class CambSpeaker(BaseSpeaker):
    def __init__(self):
        self.api_key = settings.camb_api_key
        self.voice_id = settings.camb_voice_id

        if not self.api_key or not self.voice_id:
            raise ValueError(
                "\n\n  ❌  No CAMB.ai API Key or Voice ID configured.\n"
                "  Run 'yumi attune' or open ⚙️ Configure Senses and set them up.\n"
                "  Find your Voice ID at: https://client.camb.ai/\n"
            )

    async def stream_speak(self, text: str) -> AsyncGenerator[Any, None]:
        """Async generator that yields raw PCM audio chunks."""
        if not text:
            return

        if len(text) > 495:
            print(f"Warning: Text too long for CAMB.ai ({len(text)} chars), truncating.")
            text = text[:495] + "..."

        url = "https://client.camb.ai/apis/tts-stream"
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

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
                            data_idx = buffer.find(b"data")
                            if data_idx != -1 and len(buffer) >= data_idx + 8:
                                sample_rate = struct.unpack("<I", buffer[24:28])[0]
                                yield {"type": "metadata", "sampleRate": sample_rate}
                                audio_data = buffer[data_idx + 8:]
                                if audio_data:
                                    yield base64.b64encode(audio_data).decode("utf-8")
                                is_first_chunk = False
                                buffer = b""
                        else:
                            yield base64.b64encode(chunk).decode("utf-8")

        except Exception as e:
            print(f"Error speaking response from CAMB.ai: {e}")

    def speak(self, text: str, streaming: bool = False) -> tuple[str | None, float]:
        """Sychronous wrapper for stream_speak.
        Note: Since stream_speak is async, we need to run this in a loop.
        Because this method is defined as synchronous in the interface for legacy reasons,
        it's better to use the streaming version.
        """
        # This is a bridge for the interface.
        # In a production-grade version, we would handle the loop here or avoid sync speak.
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We are already in a loop, cannot run another.
                # Returning None as we can't easily block here.
                return None, 0.0

            # Accumulate the stream into a single block
            chunks = []
            async def collect():
                async for chunk in self.stream_speak(text):
                    if isinstance(chunk, str):
                        chunks.append(chunk)

            loop.run_until_complete(collect())
            full_audio = ",".join(chunks) # Simplified
            return full_audio, 0.0
        except Exception as e:
            print(f"Sync speak error: {e}")
            return None, 0.0
