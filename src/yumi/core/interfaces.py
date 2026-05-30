"""Abstract Base Classes defining Yumi's core pluggable interfaces.

Defines the contracts for Text-to-Speech (TTS) and Speech-to-Text (STT) providers.
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Any

class BaseSpeaker(ABC):
    """Abstract Base Class for Yumi's TTS (Text-to-Speech) providers."""

    @abstractmethod
    async def stream_speak(self, text: str) -> AsyncGenerator[Any, None]:
        """Synthesize text and yield audio chunks.

        The first yield should ideally be metadata (e.g., sample rate),
        followed by audio data chunks.
        """
        pass

    @abstractmethod
    def speak(self, text: str, streaming: bool = False) -> tuple[str | None, float]:
        """Perform blocking synthesis for non-streaming requests.

        Returns:
            A tuple of (base64_audio_string, duration_seconds).

        """
        pass

class BaseSTTProvider(ABC):
    """Abstract Base Class for Yumi's STT (Speech-to-Text) providers."""

    @abstractmethod
    async def transcribe(self, audio_data: Any) -> str | None:
        """Convert raw audio data to text."""
        pass
