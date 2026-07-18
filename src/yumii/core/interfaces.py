"""Abstract base classes for Yumii's TTS and STT providers."""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator


class BaseSpeaker(ABC):
    """Abstract base class for TTS (Text-to-Speech) providers."""

    @abstractmethod
    async def stream_speak(self, text: str) -> AsyncGenerator[Any, None]:
        """Synthesize text and yield audio chunks (first yield is metadata)."""
        pass

    @abstractmethod
    def speak(self, text: str, streaming: bool = False) -> tuple[str | None, float]:
        """Blocking synthesis. Returns ``(base64_audio, duration_seconds)``."""
        pass


class BaseSTTProvider(ABC):
    """Abstract base class for STT (Speech-to-Text) providers.

    ``transcribe`` may block (the engine runs it in a worker thread);
    streaming providers may additionally expose ``process_chunk`` / ``get_final``.
    """

    @abstractmethod
    def transcribe(self, audio_data: Any) -> str | None:
        """Convert raw audio data to text. May block; runs off the event loop."""
        pass
