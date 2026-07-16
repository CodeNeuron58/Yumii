"""Core reasoning and execution engine for Yumii.

This module orchestrates the background tasks for audio capture, LLM reasoning,
and TTS synthesis, passing data between them using asyncio Queues.
"""


from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Dict, List

import aiosqlite
from fastapi import WebSocket
from langchain_core.messages import AIMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from yumii.agent.graph import _CHECKPOINT_DB, build_graph, set_confirmation_hook
from yumii.agent.synthesizer import _THINK_BLOCK, synthesize
from yumii.audio.stt import AudioPipeline
from yumii.core.config import settings
from yumii.core.interfaces import BaseSpeaker
from yumii.core.memory_db import init_db
from yumii.core.memory_manager import memory_manager
from yumii.core.session_manager import session_manager
from yumii.tts.factory import get_speaker

from yumii.core.logging import get_logger

log = get_logger(__name__)

# How many completed turns accumulate before the background memory
# review runs (Hermes's "nudge"). The reviewer sees the buffered turns
# plus existing facts and emits add/replace/remove deltas — periodic
# review over a window beats the old per-turn add-only extractor on
# both quality and LLM-call count. The buffer also flushes on session
# switch and shutdown so trailing turns aren't lost.
_MEMORY_REVIEW_INTERVAL = 5

# Spoken when the model calls a tool without saying anything alongside
# it (some models emit bare tool calls). Short and personality-neutral
# — the prompt asks her to narrate in her own voice, so these are only
# the safety net that keeps a tool turn from ever being dead air.
_TOOL_NARRATION_FILLERS = (
    "Let me check that for you.",
    "One moment.",
    "On it, give me a second.",
)


def _derive_tool_narration(output: Any, *, allow_filler: bool = True) -> str | None:
    """Spoken line for an agent pass that decided to call tools.

    A tool turn takes seconds (LLM pass → confirmation → tool call →
    final pass) and used to be dead air: the model's narration ("let
    me check your inbox") was discarded and only the final reply was
    spoken. Returns that narration (think-blocks stripped), a filler
    when the model stayed silent, or ``None`` when this pass isn't a
    tool pass / already carries the final response.

    ``allow_filler`` is True only for the FIRST tool pass of a turn:
    models sometimes chain several silent tool passes back-to-back,
    and narrating a canned filler for each ("On it… one moment… on
    it…") is worse than the silence it replaces. Later passes speak
    only words the model actually produced.
    """
    if not isinstance(output, dict) or output.get("response"):
        return None
    messages = output.get("messages") or []
    last_ai = next(
        (m for m in reversed(messages) if isinstance(m, AIMessage)), None
    )
    if last_ai is None or not getattr(last_ai, "tool_calls", None):
        return None
    raw = last_ai.content if isinstance(last_ai.content, str) else str(last_ai.content or "")
    narration = _THINK_BLOCK.sub("", raw).strip()
    if not narration:
        if not allow_filler:
            return None
        import random

        narration = random.choice(_TOOL_NARRATION_FILLERS)
    return narration


def _classify_turn_error(exc: Exception) -> tuple[str, str]:
    """Map a reasoning failure to (kind, user-facing message).

    So the orb can show a clear, actionable card instead of a frozen
    'Thinking…' — the #1 first-run failure (bad or missing LLM key)
    finally says what's wrong.
    """
    text = str(exc).lower()
    if any(
        s in text
        for s in (
            "401", "403", "unauthorized", "invalid api key", "invalid_api_key",
            "authentication", "no api key", "requires a subscription",
        )
    ):
        return (
            "auth",
            "I can't reach my mind — the API key doesn't seem to be working. "
            "Mind checking it in the dashboard?",
        )
    if any(
        s in text
        for s in ("429", "rate limit", "rate_limit", "quota", "insufficient", "capacity", "overloaded")
    ):
        return (
            "quota",
            "I've hit my thinking limit for now. Give it a little while and try me again.",
        )
    if any(
        s in text
        for s in ("connection", "timed out", "timeout", "getaddrinfo", "unreachable", "connect", "network")
    ):
        return (
            "network",
            "I can't reach my mind right now — is the connection okay?",
        )
    return (
        "generic",
        "Something glitched on my end mid-thought. Say that again for me?",
    )


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
        # ``None`` is the mute sentinel — it tells an in-flight capture
        # in the audio pipeline to reset (see AudioPipeline.stream_capture).
        self.audio_input_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.interrupt_event: asyncio.Event = asyncio.Event()
        self.active_connections: List[WebSocket] = []
        self.is_speaking: bool = False
        # Manual mic mute (user-controlled from the orb). Gates listening
        # only — speaking, reasoning, and the WS all keep running.
        self.mic_muted: bool = False
        self.active_session_id: str | None = None
        self.active_session_name: str = "New Chat"

        # PR 4: HITL confirmation gate. Pending confirmations are
        # keyed by request_id (a UUID minted when the engine asks the
        # browser). The future is set by the WS server when the user
        # replies (or auto-resolved to False on timeout). See
        # :meth:`request_confirmation` and
        # :meth:`resolve_confirmation`.
        self.pending_confirmations: dict[str, "asyncio.Future[bool]"] = {}

        # Turns since the last background memory review, and the buffer
        # of (role, content) dicts the reviewer will see.
        self._memory_turn_buffer: list[dict[str, str]] = []

        # Episodic block injected into the system prompt: time since
        # last talk + recent conversation summaries. Rebuilt at session
        # start and refreshed as the live session grows (summarizer.py).
        self.session_context: str = ""
        self._session_msg_count: int = 0

        self.stt_provider: str = settings.stt_provider
        self.model_size: str = settings.whisper_model_size
        self.groq_api_key: str | None = settings.groq_api_key

        # Audio (STT + TTS) is prepared AFTER the server is up, so the
        # first launch can download the local models behind a progress
        # screen in the orb instead of stalling boot (or the first spoken
        # word). ``pipeline`` and ``speaker`` stay None until then.
        self.pipeline: AudioPipeline | None = None
        self.speaker: BaseSpeaker | None = None
        self.audio_ready: bool = False
        # Consumed by /api/status and shown by the orb. ``progress`` is
        # 0..1; ``indeterminate`` marks a stage with no byte-level %.
        self.model_status: dict[str, Any] = {
            "ready": False,
            "stage": "starting",
            "progress": 0.0,
            "indeterminate": False,
        }

        # graph_app is initialized lazily via initialize() because
        # AsyncSqliteSaver requires an async context. The saver is kept
        # so reload_tools() can rebuild the graph on the same
        # checkpoint store.
        self.graph_app: Any | None = None
        self._conn: aiosqlite.Connection | None = None
        self._saver: AsyncSqliteSaver | None = None

    async def initialize(self) -> None:
        """Async one-time initialization: database tables + compiled graph."""
        log.info("engine_initializing")
        await init_db()

        # Load Composio tools for the user's connected apps BEFORE the
        # graph is built, so bind_tools sees them. Every Composio tool
        # is HITL-gated by default; failures are logged inside the
        # loader and never block boot.
        from yumii.tools.composio_loader import load_and_register_composio_tools

        composio_tools = await load_and_register_composio_tools()
        if composio_tools:
            log.info("composio_ready", count=len(composio_tools))

        # Open the SQLite connection directly and keep it alive for the
        # engine lifetime.  AsyncSqliteSaver.from_conn_string() is a
        # short-lived context manager; using it here would GC-close the
        # connection after the first turn and crash on restart.
        _CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(_CHECKPOINT_DB))
        self._saver = AsyncSqliteSaver(self._conn)
        self.graph_app = await build_graph(checkpointer=self._saver)
        # PR 4: install the HITL confirmation hook so the gated
        # tools node knows who to ask when a tool needs approval.
        set_confirmation_hook(self._confirmation_hook)

        # One-time transcript backfill: conversations that predate the
        # searchable transcript live only in LangGraph checkpoints, which
        # can't be searched. Copy them over once so recall covers the
        # user's whole history, not just turns after this upgrade.
        try:
            await self._backfill_transcript_once()
        except Exception:
            log.warning("transcript_backfill_failed", exc_info=True)

        # Prepare audio (download local models, build STT + TTS, start
        # the interaction loops) in the background so the server is
        # already responding to /health and /api/status while the orb
        # shows download progress.
        asyncio.create_task(self._prepare_audio())

        log.info("engine_ready")

    async def _prepare_audio(self) -> None:
        """Download local models (with progress), build the STT pipeline
        and TTS speaker, then start the three interaction loops.

        Runs off the boot path so the server stays responsive during the
        first-launch model download. Retries on failure so a flaky
        download never leaves her permanently deaf — the orb keeps
        showing progress and she recovers on her own.
        """
        from yumii.core.models import ensure_models_ready

        def on_progress(stage: str, frac: float | None) -> None:
            self.model_status = {
                "ready": False,
                "stage": stage,
                "progress": frac if frac is not None else self.model_status.get("progress", 0.0),
                "indeterminate": frac is None,
            }

        while not self.audio_ready:
            try:
                await asyncio.to_thread(ensure_models_ready, on_progress)
                # Models are on disk now — load them (heavy, off-loop).
                self.pipeline = await asyncio.to_thread(self._build_pipeline)
                self.speaker = await asyncio.to_thread(get_speaker)
                self.audio_ready = True
                self.model_status = {
                    "ready": True,
                    "stage": "ready",
                    "progress": 1.0,
                    "indeterminate": False,
                }
                asyncio.create_task(self.audio_listener_task())
                asyncio.create_task(self.reasoning_engine_task())
                asyncio.create_task(self.tts_speaker_task())
                log.info("audio_ready")
            except Exception:
                log.error("audio_prepare_failed_retrying", exc_info=True)
                self.model_status = {
                    "ready": False,
                    "stage": "error",
                    "progress": self.model_status.get("progress", 0.0),
                    "indeterminate": False,
                }
                await asyncio.sleep(3)

    def _build_pipeline(self) -> AudioPipeline:
        log.info("audio_pipeline_init", stt_provider=self.stt_provider)
        return AudioPipeline(
            provider=self.stt_provider,
            model_size=self.model_size,
            groq_api_key=self.groq_api_key,
        )

    async def _backfill_transcript_once(self) -> None:
        """Populate the transcript from checkpoints, first boot only.

        Runs only when the transcript is completely empty (fresh upgrade)
        — any recorded message means backfill already happened or normal
        recording is underway. Timestamps are approximated with each
        session's created_at (checkpoints don't store per-message times).
        """
        from langchain_core.messages import AIMessage, HumanMessage

        from yumii.core import transcript

        if not await transcript.is_empty():
            return
        sessions = await session_manager.list_sessions(
            include_archived=True, limit=1000
        )
        if not sessions:
            return

        total = 0
        for session in sessions:
            try:
                state = await self.graph_app.aget_state(
                    {"configurable": {"thread_id": session.id}}
                )
                messages = (state.values or {}).get("messages", []) if state else []
                turns: list[tuple[str, str]] = []
                for m in messages:
                    content = m.content if isinstance(m.content, str) else str(m.content)
                    if not content.strip():
                        continue
                    if isinstance(m, HumanMessage):
                        turns.append(("user", content))
                    elif isinstance(m, AIMessage) and not getattr(m, "tool_calls", None):
                        turns.append(("assistant", content))
                total += await transcript.record_many(
                    session.id, turns, created_at=session.created_at
                )
            except Exception:
                log.warning(
                    "transcript_backfill_session_failed",
                    session_id=session.id,
                    exc_info=True,
                )
        if total:
            log.info(
                "transcript_backfilled", sessions=len(sessions), messages=total
            )

    async def reload_tools(self) -> list[str]:
        """Re-fetch Composio tools and rebuild the agent graph in place.

        Called by the dashboard endpoints after the user connects or
        disables a toolkit, so tool changes apply without an app
        restart. Conversation history is untouched (same checkpointer);
        an in-flight turn keeps the old graph object and finishes on it.

        Returns the Composio tool names now registered.
        """
        from yumii.agent.llm import clear_llm_cache
        from yumii.tools.composio_loader import load_and_register_composio_tools

        registered = await load_and_register_composio_tools()
        # The shared tool binding caches the old tool list — drop it so
        # the next turn binds the new registry contents.
        clear_llm_cache()
        if self._saver is not None:
            self.graph_app = await build_graph(checkpointer=self._saver)
        log.info("tools_reloaded", composio_count=len(registered))
        return registered

    def _flush_memory_review(self, session_id: str | None = None) -> None:
        """Fire the background memory review over the buffered turns."""
        if not self._memory_turn_buffer:
            return
        turns = self._memory_turn_buffer
        self._memory_turn_buffer = []
        asyncio.create_task(
            memory_manager.review_recent_turns(
                turns, session_id or self.active_session_id
            )
        )

    async def _rebuild_session_context(self, *, include_current: bool) -> None:
        """Recompute the episodic prompt block (never lets a failure block)."""
        from yumii.core.summarizer import build_session_context

        try:
            self.session_context = await build_session_context(
                self.active_session_id or "", include_current=include_current
            )
        except Exception:
            log.warning("session_context_build_failed", exc_info=True)
            self.session_context = ""

    async def _finalize_session(self, session_id: str) -> None:
        """Summarize an ended session, then refresh the episodic block
        so the just-finished conversation shows up in it."""
        from yumii.core.summarizer import summarize_session

        try:
            await summarize_session(session_id)
            # include_current is harmless when the active session has no
            # summary row yet — the "Earlier in this conversation" line
            # is simply omitted.
            await self._rebuild_session_context(include_current=True)
        except Exception:
            log.warning("session_finalize_failed", session_id=session_id, exc_info=True)

    async def shutdown(self) -> None:
        """Clean shutdown: close SQLite connections and memory store."""
        log.info("engine_shutting_down")

        # Review any turns still buffered — quitting the app must not
        # lose what the user just told her. Bounded so a slow provider
        # can't hang the exit.
        if self._memory_turn_buffer:
            turns, self._memory_turn_buffer = self._memory_turn_buffer, []
            try:
                await asyncio.wait_for(
                    memory_manager.review_recent_turns(
                        turns, self.active_session_id
                    ),
                    timeout=20.0,
                )
            except Exception:
                log.warning("shutdown_memory_review_failed", exc_info=True)

        # Summarize the session that's ending so the next boot's
        # "Recent conversations" block includes it. Same bound.
        if self.active_session_id and self._session_msg_count > 0:
            try:
                from yumii.core.summarizer import summarize_session

                await asyncio.wait_for(
                    summarize_session(self.active_session_id), timeout=20.0
                )
            except Exception:
                log.warning("shutdown_session_summary_failed", exc_info=True)

        if self._conn is not None:
            try:
                await self._conn.close()
            except Exception:
                pass
            self._conn = None
        await memory_manager.close()

    # ------------------------------------------------------------------
    # Manual mic mute
    # ------------------------------------------------------------------

    async def set_mic_muted(self, muted: bool) -> None:
        """Gate the listening pipeline without disturbing the active loop.

        The mic stream, WebSocket, and all three engine tasks keep
        running — muting only stops audio from entering the pipeline.
        Muting also abandons any half-captured utterance (drain the
        queue, then push the ``None`` sentinel that resets the capture
        state), so words spoken just before the mute can't complete
        into a turn when the user unmutes later. Speaking and
        reasoning are unaffected: she can finish her reply while muted.
        """
        if muted == self.mic_muted:
            return
        self.mic_muted = muted
        if muted:
            while not self.audio_input_queue.empty():
                try:
                    self.audio_input_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            await self.audio_input_queue.put(None)
        log.info("mic_mute_set", muted=muted)

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def create_new_session(self, name: str | None = None) -> str:
        """Create a new session, clear all queues, and set it active."""
        # Review + summarize what the outgoing session left behind.
        previous_session = self.active_session_id
        self._flush_memory_review()
        await self._clear_all_queues()
        self.interrupt_event.clear()
        self.is_speaking = False

        session_id = await session_manager.create_session(name)
        self.active_session_id = session_id
        self.active_session_name = name or "New Chat"
        self._session_msg_count = 0
        await self._rebuild_session_context(include_current=False)
        if previous_session:
            asyncio.create_task(self._finalize_session(previous_session))

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

        # Review + summarize what the outgoing session left behind.
        previous_session = self.active_session_id
        self._flush_memory_review()
        await self._clear_all_queues()
        self.interrupt_event.clear()
        self.is_speaking = False

        self.active_session_id = session.id
        self.active_session_name = session.name
        self._session_msg_count = 0
        await session_manager.update_session_activity(session.id)
        # include_current: on resume, "Earlier in this conversation: …"
        # bridges whatever the history window no longer carries.
        await self._rebuild_session_context(include_current=True)
        if previous_session and previous_session != session.id:
            asyncio.create_task(self._finalize_session(previous_session))

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
                if hasattr(self.pipeline.transcriber, "process_chunk"):
                    async def on_partial(text: str):
                        await self.broadcast_payload({
                            "type": "partial_transcript",
                            "text": text
                        })
                    
                    transcribed_text = await self.pipeline.stream_capture_and_transcribe(
                        self.audio_input_queue, on_speech_start, on_partial
                    )
                    if transcribed_text and transcribed_text.strip():
                        # Let the text remain on screen until Yumii starts speaking.
                        log.info("transcription_complete", text=transcribed_text)
                        await self.transcription_queue.put(transcribed_text)
                else:
                    audio_segment = await self.pipeline.stream_capture(
                        self.audio_input_queue, on_speech_start
                    )
                    if audio_segment is not None and len(audio_segment) > 0:
                        processed_audio = self.pipeline.process_audio(audio_segment)
                        if len(processed_audio) > 0:
                            # Whisper inference / the Groq HTTP call can take
                            # seconds — run it off the event loop so the WS,
                            # TTS streaming, and interrupts stay responsive.
                            transcribed_text = await asyncio.to_thread(
                                self.pipeline.transcribe, processed_audio
                            )
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

                # Initial state for the graph. turn_id scopes message
                # IDs: stable across agent passes within this turn (so
                # add_messages dedupes the re-added HumanMessage) but
                # unique across turns (so repeating the same phrase
                # later doesn't overwrite the earlier message).
                turn_id = uuid.uuid4().hex
                initial_state = {
                    "input": user_text,
                    "turn_id": turn_id,
                    "session_id": self.active_session_id,
                    "session_name": self.active_session_name,
                    "user_facts": facts,
                    "session_context": self.session_context,
                }

                reasoning_result: dict | None = None
                streamed_delta_count = 0
                tool_passes_narrated = 0
                last_narration: str | None = None
                turn_error: tuple[str, str] | None = None  # (kind, message)

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
                            else:
                                # Tool pass: speak the model's narration
                                # (or, on the first pass only, a short
                                # filler) NOW, while the tools run — the
                                # queue is FIFO, so the real answer
                                # follows right after. A 20-second Gmail
                                # fetch is no longer dead air. Repeats
                                # of the same line are suppressed so a
                                # model looping on a tool doesn't chant.
                                narration = _derive_tool_narration(
                                    output,
                                    allow_filler=tool_passes_narrated == 0,
                                )
                                if (
                                    narration
                                    and narration != last_narration
                                    and not self.interrupt_event.is_set()
                                ):
                                    tool_passes_narrated += 1
                                    last_narration = narration
                                    spoken = synthesize(narration)
                                    log.info(
                                        "tool_narration", text=spoken.response_text[:80]
                                    )
                                    await self.tts_queue.put(
                                        {
                                            "response": spoken.response_text,
                                            "expression": spoken.expression,
                                            "motion": spoken.motion,
                                        }
                                    )
                except Exception as stream_exc:
                    log.error(
                        "reasoning_stream_error",
                        error=str(stream_exc),
                        exc_info=True,
                    )
                    turn_error = _classify_turn_error(stream_exc)

                # Always close the thinking indicator, even on error.
                await self.broadcast_payload({"type": "thinking_end"})

                if self.interrupt_event.is_set():
                    log.info("reasoning_interrupted")
                    continue

                # A hard failure with nothing to say: surface a clear,
                # actionable card (never a silent frozen "Thinking…").
                # Skip the spoken generic apology — the card is clearer,
                # and an auth error means she couldn't think at all.
                if reasoning_result is None and turn_error is not None:
                    kind, message = turn_error
                    log.info("turn_error_surfaced", kind=kind)
                    await self.broadcast_payload(
                        {"type": "error", "kind": kind, "message": message}
                    )
                    continue

                # Fallback: the stream ended without capturing the
                # agent's final output. NEVER re-invoke the graph here
                # — the stream may already have executed tools before
                # failing, and a re-run would execute them again
                # (double email send). Instead read what the
                # checkpoint recorded; response_turn_id tells a fresh
                # response apart from last turn's leftovers.
                if reasoning_result is None:
                    log.warning("reasoning_no_streamed_output_reading_state")
                    try:
                        state = await self.graph_app.aget_state(config)
                        values = (state.values or {}) if state else {}
                        if (
                            values.get("response")
                            and values.get("response_turn_id") == turn_id
                        ):
                            reasoning_result = {
                                "response": values["response"],
                                "expression": values.get("expression", "normal"),
                                "motion": values.get("motion", "idle"),
                            }
                    except Exception:
                        log.error("reasoning_state_read_failed", exc_info=True)
                if reasoning_result is None:
                    reasoning_result = {
                        "response": (
                            "Mm, something glitched on my end mid-thought. "
                            "Say that again for me?"
                        ),
                        "expression": "sad",
                        "motion": "shakehead",
                    }

                log.debug(
                    "reasoning_done",
                    streamed_deltas=streamed_delta_count,
                    response_len=len(reasoning_result.get("response", "")),
                )

                # Book-keeping after a successful turn: bump the message
                # count, touch activity, and auto-title the session from
                # the first utterance.
                await session_manager.bump_after_turn(
                    self.active_session_id, user_text
                )

                # Append the turn to the searchable transcript so the
                # recall tool can find it in any future conversation.
                try:
                    from yumii.core import transcript

                    await transcript.record_turn(
                        self.active_session_id,
                        user_text,
                        reasoning_result["response"],
                    )
                except Exception:
                    log.warning("transcript_record_failed", exc_info=True)

                # Long-session continuity: refresh this session's summary
                # every SUMMARY_REFRESH_MESSAGES so early turns that slid
                # out of the history window survive in the prompt block.
                self._session_msg_count += 2
                from yumii.core.summarizer import SUMMARY_REFRESH_MESSAGES

                if self._session_msg_count % SUMMARY_REFRESH_MESSAGES == 0:
                    asyncio.create_task(
                        self._finalize_session(self.active_session_id)
                    )
                if self.active_session_name == "New Chat":
                    refreshed = await session_manager.get_session(
                        self.active_session_id
                    )
                    if refreshed:
                        self.active_session_name = refreshed.name

                # Buffer the turn for the periodic memory review. Every
                # _MEMORY_REVIEW_INTERVAL turns a background reviewer
                # sees the buffer + existing facts and emits deltas
                # (replaces the old per-turn add-only extraction — the
                # agent can also write memory directly via the
                # manage_memory tool for "remember this" moments).
                self._memory_turn_buffer.extend(
                    [
                        {"role": "user", "content": user_text},
                        {"role": "assistant", "content": reasoning_result["response"]},
                    ]
                )
                if len(self._memory_turn_buffer) >= _MEMORY_REVIEW_INTERVAL * 2:
                    self._flush_memory_review()

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
