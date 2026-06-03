"""
Core reasoning and execution engine for Yumi.

This module orchestrates the background tasks for audio capture, LLM reasoning,
and TTS synthesis, passing data between them using asyncio Queues.
"""


import asyncio
import json
from typing import Any, Dict, List

from fastapi import WebSocket

from yumi.agent.graph import build_graph
from yumi.audio.stt import AudioPipeline
from yumi.core.config import settings
from yumi.core.interfaces import BaseSpeaker
from yumi.tts.factory import get_speaker

from yumi.core.logging import get_logger
log = get_logger(__name__)


class YumiEngine:
    """The central orchestration engine for Yumi.

    This class encapsulates the state and logic required to run the real-time
    interaction loop, decoupling the audio processing and reasoning from
    the transport layer (FastAPI).
    """

    def __init__(self) -> None:
        """Initialize the Yumi Engine, including audio pipelines and reasoning graph."""
        self.transcription_queue: asyncio.Queue[str] = asyncio.Queue()
        self.tts_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self.audio_input_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.interrupt_event: asyncio.Event = asyncio.Event()
        self.active_connections: List[WebSocket] = []
        self.is_speaking: bool = False

        self.stt_provider: str = settings.stt_provider
        self.model_size: str = settings.whisper_model_size
        self.groq_api_key: str | None = settings.groq_api_key

        log.info("audio_pipeline_init", stt_provider=self.stt_provider)
        self.pipeline = AudioPipeline(
            provider=self.stt_provider,
            model_size=self.model_size,
            groq_api_key=self.groq_api_key,
        )

        log.info("speaker_init")
        self.speaker: BaseSpeaker = get_speaker()

        self.graph_app = build_graph()

    async def broadcast_payload(self, payload: Dict[str, Any]) -> None:
        """Push a JSON payload to all currently connected WebSocket clients.

        Args:
            payload: The dictionary to be serialized and sent as a message.

        """
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(payload))
            except Exception as e:
                log.warning("ws_send_error", error=str(e))
                dead_connections.append(connection)
        for dead in dead_connections:
            if dead in self.active_connections:
                self.active_connections.remove(dead)

    async def audio_listener_task(self) -> None:
        """Continuously monitors the audio input queue.

        Triggers the global interrupt event and notifies the frontend when speech is detected,
        and pushes completed transcriptions to the reasoning queue.
        """

        def on_speech_start() -> None:
            # We allow interrupts even while speaking to achieve a "Gemini Live" feel.
            # The browser's `echoCancellation` and Silero VAD handle the filtering
            # of Yumi's own voice, but we *also* suppress the interrupt event
            # while audio is actively playing on the TTS speaker. This is a
            # belt-and-suspenders defense against the feedback loop that would
            # otherwise occur when the user's mic picks up Yumi's spoken output
            # on speakers without headphones.
            if self.is_speaking:
                log.debug("interrupt_suppressed_yumi_speaking")
                return
            self.interrupt_event.set()
            payload = {"type": "interrupt"}
            asyncio.create_task(self.broadcast_payload(payload))

        log.info("listener_task_started")
        while True:
            try:
                audio_segment = await self.pipeline.stream_capture(
                    self.audio_input_queue, on_speech_start
                )
                if audio_segment is not None and len(audio_segment) > 0:
                    processed_audio = self.pipeline.process_audio(audio_segment)
                    if len(processed_audio) > 0:
                        transcribed_text = self.pipeline.transcribe(processed_audio)
                        if transcribed_text and transcribed_text.strip():
                            log.info("transcription_complete", text=transcribed_text)
                            await self.transcription_queue.put(transcribed_text)
            except Exception as e:
                log.error("audio_listener_crash", error=str(e), exc_info=True)
                await asyncio.sleep(1)

    async def reasoning_engine_task(self) -> None:
        """Execute the main reasoning loop.

        Waits for transcribed text, clears any active interruptions,
        and invokes the LangGraph reasoning engine to generate a response.
        """
        session_id = "yumi_session_1"
        config = {"configurable": {"thread_id": session_id}}
        log.info("reasoning_task_started")
        while True:
            try:
                user_text = await self.transcription_queue.get()
                self.interrupt_event.clear()

                # Clear pending speech queue on new input
                while not self.tts_queue.empty():
                    try:
                        self.tts_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                log.debug("reasoning_start", user_text=user_text)
                reasoning_result = await self.graph_app.ainvoke(
                    {"input": user_text, "session_id": session_id}, config=config
                )

                if self.interrupt_event.is_set():
                    log.info("reasoning_interrupted")
                    continue

                await self.tts_queue.put(reasoning_result)
            except Exception as e:
                log.error("reasoning_engine_crash", error=str(e), exc_info=True)
                await asyncio.sleep(1)

    async def tts_speaker_task(self) -> None:
        """Run the voice synthesis loop.

        Consumes reasoning results and uses the active TTS provider to
        stream audio chunks to the frontend.
        """
        log.info("speaker_task_started")
        while True:
            try:
                speech_payload = await self.tts_queue.get()
                if self.interrupt_event.is_set():
                    continue

                response_text = speech_payload["response"]
                expression = speech_payload.get("expression", "normal")
                motion = speech_payload.get("motion", "idle")

                log.info("yumi_response", text=response_text)

                self.is_speaking = True

                # Handle providers that support the streaming interface
                if hasattr(self.speaker, "stream_speak"):
                    try:
                        async for chunk_data in self.speaker.stream_speak(
                            response_text
                        ):
                            if self.interrupt_event.is_set():
                                break

                            if (
                                isinstance(chunk_data, dict)
                                and chunk_data.get("type") == "metadata"
                            ):
                                await self.broadcast_payload(
                                    {
                                        "type": "audio_start",
                                        "sampleRate": chunk_data["sampleRate"],
                                        "text": response_text,
                                        "expression": expression,
                                        "motion": motion,
                                    }
                                )
                            else:
                                await self.broadcast_payload(
                                    {"type": "audio_chunk", "data": chunk_data}
                                )
                        if not self.interrupt_event.is_set():
                            await self.broadcast_payload({"type": "audio_end"})
                    except Exception as stream_err:
                        log.error("tts_stream_error", error=str(stream_err), exc_info=True)
                        await self.broadcast_payload(
                            {
                                "text": response_text,
                                "expression": expression,
                                "motion": motion,
                                "audio": None,
                                "error": f"TTS failed: {stream_err}",
                            }
                        )
                else:
                    # Fallback for non-streaming providers
                    audio_b64, duration = await asyncio.to_thread(
                        self.speaker.speak, response_text
                    )
                    if self.interrupt_event.is_set():
                        continue
                    await self.broadcast_payload(
                        {
                            "text": response_text,
                            "expression": expression,
                            "motion": motion,
                            "audio": audio_b64,
                        }
                    )
                    if duration > 0:
                        slept = 0.0
                        while slept < (duration + 0.5):
                            if self.interrupt_event.is_set():
                                break
                            await asyncio.sleep(0.1)
                            slept += 0.1

                self.is_speaking = False

            except Exception as e:
                log.error("tts_speaker_crash", error=str(e), exc_info=True)
                await asyncio.sleep(1)
