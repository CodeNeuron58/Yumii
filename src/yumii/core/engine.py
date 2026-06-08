"""Core reasoning and execution engine for Yumii.

This module orchestrates the background tasks for audio capture, LLM reasoning,
and TTS synthesis, passing data between them using asyncio Queues.
"""


from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List

import aiosqlite
from fastapi import WebSocket
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from yumii.agent.graph import _CHECKPOINT_DB, build_graph, set_confirmation_hook
from yumii.audio.stt import AudioPipeline
from yumii.core.config import settings
from yumii.core.interfaces import BaseSpeaker
from yumii.core.memory_db import init_db
from yumii.core.memory_manager import memory_manager
from yumii.core.session_manager import session_manager
from yumii.tts.factory import get_speaker

from yumii.core.logging import get_logger

log = get_logger(__name__)

class YumiiEngine:
    """The central orchestration engine for Yumii.

    This class encapsulates the state and logic required to run the real-time
    interaction loop, decoupling the audio processing and reasoning from
    the transport layer (FastAPI).
    """

    def __init__(self) -> None:
        """Initialize the Yumii Engine, including audio pipelines and reasoning graph."""
        self.transcription_queue: asyncio.Queue[str] = asyncio.Queue()
        self.tts_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self.audio_input_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.interrupt_event: asyncio.Event = asyncio.Event()
        self.active_connections: List[WebSocket] = []
        self.is_speaking: bool = False
        self.active_session_id: str | None = None
        self.active_session_name: str = "New Chat"

        # PR 4: HITL confirmation gate. Pending confirmations are
        # keyed by request_id (a UUID minted when the engine asks the
        # browser). The future is set by the WS server when the user
        # replies (or auto-resolved to False on timeout). See
        # :meth:`request_confirmation` and
        # :meth:`resolve_confirmation`.
        self.pending_confirmations: dict[str, "asyncio.Future[bool]"] = {}

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

        # graph_app is initialized lazily via initialize() because
        # AsyncSqliteSaver requires an async context.
        self.graph_app: Any | None = None
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Async one-time initialization: database tables + compiled graph."""
        log.info("engine_initializing")
        await init_db()

        # Open the SQLite connection directly and keep it alive for the
        # engine lifetime.  AsyncSqliteSaver.from_conn_string() is a
        # short-lived context manager; using it here would GC-close the
        # connection after the first turn and crash on restart.
        _CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(_CHECKPOINT_DB))
        saver = AsyncSqliteSaver(self._conn)
        self.graph_app = await build_graph(checkpointer=saver)
        # PR 4: install the HITL confirmation hook so the gated
        # tools node knows who to ask when a tool needs approval.
        set_confirmation_hook(self._confirmation_hook)
        log.info("engine_ready")

    async def shutdown(self) -> None:
        """Clean shutdown: close SQLite connections and memory store."""
        log.info("engine_shutting_down")
        if self._conn is not None:
            try:
                await self._conn.close()
            except Exception:
                pass
            self._conn = None
        await memory_manager.close()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def create_new_session(self, name: str | None = None) -> str:
        """Create a new session, clear all queues, and set it active."""
        await self._clear_all_queues()
        self.interrupt_event.clear()
        self.is_speaking = False

        session_id = await session_manager.create_session(name)
        self.active_session_id = session_id
        self.active_session_name = name or "New Chat"

        facts = await memory_manager.get_facts_raw()
        log.info(
            "session_created_and_active",
            session_id=session_id,
            name=self.active_session_name,
            fact_count=len(facts),
        )
        return session_id

    async def resume_session(self, session_id: str) -> str:
        """Resume an existing session, or create a new one if the ID is invalid."""
        session = await session_manager.get_session(session_id)
        if not session:
            log.warning("session_not_found", session_id=session_id)
            return await self.create_new_session(name=f"Resumed-{session_id[:8]}")

        await self._clear_all_queues()
        self.interrupt_event.clear()
        self.is_speaking = False

        self.active_session_id = session.id
        self.active_session_name = session.name
        await session_manager.update_session_activity(session.id)

        facts = await memory_manager.get_facts_raw()
        log.info(
            "session_resumed",
            session_id=session.id,
            name=session.name,
            fact_count=len(facts),
        )
        return session.id

    async def _clear_all_queues(self) -> None:
        """Drain all internal queues so no stale audio / text bleeds across sessions."""
        for q in (self.tts_queue, self.transcription_queue, self.audio_input_queue):
            while not q.empty():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    break
        log.debug("queues_cleared")

    # ------------------------------------------------------------------
    # Broadcast
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # HITL confirmation gate (PR 4)
    # ------------------------------------------------------------------

    async def _confirmation_hook(
        self,
        request_id: str,
        tool_name: str,
        tool_args: dict,
    ) -> bool:
        """Bridge between the gated tools node and the WS layer.

        The graph calls this with a freshly-minted ``request_id``.
        We delegate to :meth:`request_confirmation` (which broadcasts
        the WS event and awaits the reply). If the user barge-ins
        mid-confirmation, we resolve as a deny so the LLM gets
        feedback and the loop can short-circuit.
        """
        # Pre-check: if the user has already interrupted (e.g. they
        # said "stop" while the gate was being prepared), deny
        # immediately.
        if self.interrupt_event.is_set():
            log.info("confirmation_bypass_interrupt", tool=tool_name)
            return False

        approved = await self.request_confirmation(
            request_id=request_id,
            tool_name=tool_name,
            tool_args=tool_args,
        )

        # Post-check: a barge-in during the wait also counts as deny.
        if self.interrupt_event.is_set() and approved:
            log.info("confirmation_vetoed_by_interrupt", tool=tool_name)
            approved = False

        return approved

    async def request_confirmation(
        self,
        request_id: str,
        tool_name: str,
        tool_args: dict,
        timeout: float | None = None,
    ) -> bool:
        """Ask the browser to confirm a tool call; await the reply.

        Broadcasts a ``confirmation_request`` event with the tool
        name + args + request_id, then blocks (with optional timeout)
        until :meth:`resolve_confirmation` is called by the WS server
        or the timeout fires.

        Returns ``True`` if the user approved, ``False`` on deny,
        timeout, or barge-in interrupt. Caller is responsible for
        checking the active ``interrupt_event`` after this returns.
        """
        if timeout is None:
            timeout = settings.hitl_timeout_seconds

        await self.broadcast_payload(
            {
                "type": "confirmation_request",
                "request_id": request_id,
                "tool": tool_name,
                "args": tool_args,
                "timeout_seconds": timeout,
            }
        )

        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        self.pending_confirmations[request_id] = future

        try:
            approved = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            log.info("confirmation_timeout", request_id=request_id, tool=tool_name)
            await self.broadcast_payload(
                {
                    "type": "confirmation_timeout",
                    "request_id": request_id,
                    "tool": tool_name,
                }
            )
            approved = False
        finally:
            self.pending_confirmations.pop(request_id, None)

        return approved

    def resolve_confirmation(self, request_id: str, approved: bool) -> bool:
        """Resolve a pending confirmation. Returns ``True`` if a pending
        future was found and set, ``False`` otherwise (e.g. the
        request already timed out or was never issued)."""
        future = self.pending_confirmations.get(request_id)
        if future is None or future.done():
            return False
        future.set_result(approved)
        return True

    async def broadcast_payload(self, payload: Dict[str, Any]) -> None:
        """Push a JSON payload to all currently connected WebSocket clients."""
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

    # ------------------------------------------------------------------
    # Background tasks
    # ------------------------------------------------------------------

    async def audio_listener_task(self) -> None:
        """Continuously monitors the audio input queue.

        Triggers the global interrupt event and notifies the frontend when speech is detected,
        and pushes completed transcriptions to the reasoning queue.
        """

        def on_speech_start() -> None:
            # We allow interrupts even while speaking to achieve a "Gemini Live" feel.
            # The browser's `echoCancellation` and Silero VAD handle the filtering
            # of Yumii's own voice, but we *also* suppress the interrupt event
            # while audio is actively playing on the TTS speaker. This is a
            # belt-and-suspenders defense against the feedback loop that would
            # otherwise occur when the user's mic picks up Yumii's spoken output
            # on speakers without headphones.
            if self.is_speaking:
                log.debug("interrupt_suppressed_yumii_speaking")
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

        PR 3 wiring:
          * Streams graph events via ``astream_events(version="v3")``
            and broadcasts ``thinking_start`` / ``thinking_delta`` /
            ``thinking_end`` / ``tool_status`` so the frontend can show
            a responsive "thinking…" / "Searching the web…" indicator.
          * The actual spoken YumiiResponse is still produced by the
            synthesizer at the end of the graph run — we don't TTS
            streamed tokens (TTS synthesizes the full final text).
        """
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

                if not self.active_session_id or not self.graph_app:
                    log.warning("reasoning_skipped_no_session")
                    continue

                log.debug("reasoning_start", user_text=user_text)

                config = {
                    "configurable": {"thread_id": self.active_session_id}
                }

                # Pre-load long-term facts into state so chat_node can use them.
                facts = await memory_manager.get_facts_raw()

                # Notify frontend that reasoning has begun.
                await self.broadcast_payload({"type": "thinking_start"})

                # Initial state for the graph.
                initial_state = {
                    "input": user_text,
                    "session_id": self.active_session_id,
                    "session_name": self.active_session_name,
                    "user_facts": facts,
                }

                reasoning_result: dict | None = None
                streamed_delta_count = 0

                try:
                    async for event in self.graph_app.astream_events(
                        initial_state, config=config, version="v2"
                    ):
                        if self.interrupt_event.is_set():
                            log.info("reasoning_interrupted_mid_stream")
                            break

                        kind = event.get("event")
                        name = event.get("name", "")

                        # Token-by-token chat-model streaming. We
                        # surface these as ``thinking_delta`` so the
                        # UI can show a live typing indicator. We
                        # don't accumulate them — the graph itself
                        # finalises the AIMessage on the agent node.
                        if kind == "on_chat_model_stream":
                            chunk = event.get("data", {}).get("chunk")
                            token = getattr(chunk, "content", None) if chunk else None
                            if token:
                                streamed_delta_count += 1
                                await self.broadcast_payload(
                                    {"type": "thinking_delta", "text": token}
                                )

                        # Tool starting — show what the agent is up to.
                        elif kind == "on_tool_start":
                            await self.broadcast_payload(
                                {"type": "tool_status", "tool": name, "status": "running"}
                            )

                        # Tool finished — handy for "found N results" etc.
                        elif kind == "on_tool_end":
                            await self.broadcast_payload(
                                {"type": "tool_status", "tool": name, "status": "done"}
                            )

                        # Graph node finished — we capture the final
                        # node output (the agent's final delta) for
                        # TTS. LangGraph emits ``on_chain_end`` for
                        # each node, with the node's output in
                        # ``data["output"]``.
                        elif kind == "on_chain_end" and event.get("metadata", {}).get("langgraph_node") == "agent":
                            output = event.get("data", {}).get("output")
                            if isinstance(output, dict) and output.get("response"):
                                reasoning_result = output
                except Exception as stream_exc:
                    log.error(
                        "reasoning_stream_error",
                        error=str(stream_exc),
                        exc_info=True,
                    )

                # Always close the thinking indicator, even on error.
                await self.broadcast_payload({"type": "thinking_end"})

                if self.interrupt_event.is_set():
                    log.info("reasoning_interrupted")
                    continue

                # Fallback: if astream_events didn't yield an agent
                # final output (older LangGraph behaviour), fall back
                # to a blocking ainvoke so the conversation still
                # produces a response. This keeps us safe against
                # upstream API drift.
                if reasoning_result is None:
                    log.warning("reasoning_no_streamed_output_falling_back")
                    reasoning_result = await self.graph_app.ainvoke(
                        initial_state, config=config,
                    )

                log.debug(
                    "reasoning_done",
                    streamed_deltas=streamed_delta_count,
                    response_len=len(reasoning_result.get("response", "")),
                )

                # Touch session activity after a successful turn.
                await session_manager.update_session_activity(
                    self.active_session_id
                )

                # Fire-and-forget fact extraction from this turn.
                asyncio.create_task(
                    memory_manager.extract_facts_from_messages(
                        [
                            {"role": "user", "content": user_text},
                            {"role": "assistant", "content": reasoning_result["response"]},
                        ],
                        self.active_session_id,
                    )
                )

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

                log.info("yumii_response", text=response_text)

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
