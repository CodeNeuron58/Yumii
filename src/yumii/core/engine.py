"""Core engine: orchestrates audio capture, LLM reasoning, and TTS over asyncio queues."""


from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import aclosing
from typing import Any, Dict, List

import aiosqlite
from fastapi import WebSocket
from langchain_core.messages import AIMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from yumii.agent.graph import _CHECKPOINT_DB, build_graph, set_confirmation_hook
from yumii.agent.synthesizer import _THINK_BLOCK, content_to_text, synthesize
from yumii.audio.stt import AudioPipeline
from yumii.core.config import settings
from yumii.core.interfaces import BaseSpeaker
from yumii.core.memory_db import init_db
from yumii.core.memory_manager import memory_manager
from yumii.core.session_manager import session_manager
from yumii.tts.factory import get_speaker
from yumii.tts.sentence_stream import SentenceSegmenter

from yumii.core.logging import get_logger

log = get_logger(__name__)

# Completed turns between background memory reviews (also flushed on switch/shutdown).
_MEMORY_REVIEW_INTERVAL = 5

# If the webui hasn't confirmed playback finished this long after audio_end,
# assume it never will (closed tab / protocol drift) and disarm the gate.
_PLAYBACK_FINISHED_TIMEOUT_SEC = 30.0

# Spoken when the model calls a tool with no text of its own — never leave dead air.
_TOOL_NARRATION_FILLERS = (
    "Let me check that for you.",
    "One moment.",
    "On it, give me a second.",
)

# Short utterances that are direct commands, not chat — matched exactly
# (after normalization) so ordinary sentences never trip them. Works for
# typed input AND transcribed speech alike.
_STOP_PHRASES = {"stop", "stop it", "stop stop", "quiet", "be quiet"}
_MUTE_PHRASES = {"mute", "mute yourself"}
_UNMUTE_PHRASES = {"unmute", "unmute yourself", "you can listen"}
_NEW_CHAT_PHRASES = {"new chat", "new session", "new conversation"}
_REPEAT_PHRASES = {"repeat", "repeat that", "say that again", "come again"}


def _derive_tool_narration(output: Any, *, allow_filler: bool = True) -> str | None:
    """Spoken line for a tool-calling pass: the model's narration, a filler, or None.

    ``allow_filler`` is True only for the first tool pass of a turn, so
    chained silent passes don't chant "on it… one moment… on it…".
    """
    if not isinstance(output, dict) or output.get("response"):
        return None
    messages = output.get("messages") or []
    last_ai = next(
        (m for m in reversed(messages) if isinstance(m, AIMessage)), None
    )
    if last_ai is None or not getattr(last_ai, "tool_calls", None):
        return None
    raw = content_to_text(last_ai.content)
    narration = _THINK_BLOCK.sub("", raw).strip()
    if not narration:
        if not allow_filler:
            return None
        import random

        narration = random.choice(_TOOL_NARRATION_FILLERS)
    return narration


def _classify_turn_error(exc: Exception) -> tuple[str, str]:
    """Map a reasoning failure to (kind, user-facing message) for the orb's error card."""
    text = str(exc).lower()
    if any(
        s in text
        for s in (
            "not supported", "modelerror", "does not exist", "no such model",
        )
    ):
        return (
            "model",
            "That model isn't available on the provider anymore. "
            "Pick another one in the dashboard's Model panel — free ones come and go.",
        )
    if "internal server error" in text or (
        "500" in text and "error" in text
    ):
        return (
            "model",
            "Her mind's server just failed mid-thought — the model itself errored. "
            "Try again, or pick a different model in the dashboard (free ones can be flaky).",
        )
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
    """Central orchestration engine: runs the real-time loop, decoupled from FastAPI."""

    def __init__(self) -> None:
        """Set up queues, events, and state; the graph and audio pipeline are built later."""
        self.transcription_queue: asyncio.Queue[str] = asyncio.Queue()
        self.tts_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        # None is the mute sentinel — resets an in-flight capture.
        self.audio_input_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.interrupt_event: asyncio.Event = asyncio.Event()
        self.active_connections: List[WebSocket] = []
        self.is_speaking: bool = False
        # Monotonic id of the current speech session; the webui echoes it back
        # on playback_finished so a late report can't disarm a newer session.
        self._speak_seq: int = 0
        # Monotonic speech generation: every cancellation (barge-in, session
        # switch, new turn) bumps it; speech queued under an older generation
        # is abandoned wherever it is — queued, mid-synthesis, or mid-broadcast.
        # Unlike a clearable Event, nothing can "un-cancel" a bump, which is
        # what let old speech keep playing after barge-in / session switches.
        self._speech_generation: int = 0
        self.mic_muted: bool = False
        self.active_session_id: str | None = None
        self.active_session_name: str = "New Chat"
        # Last completed reply, for the "repeat" command.
        self._last_reply_text: str | None = None

        # Pending HITL confirmations, keyed by request_id; resolved by the WS server.
        self.pending_confirmations: dict[str, "asyncio.Future[bool]"] = {}

        # Turns pending background memory review, tagged with the session they
        # belong to — an in-flight turn may complete after a session switch.
        self._memory_turn_buffer: list[tuple[str | None, dict[str, str]]] = []

        # Every fire-and-forget task lives here: bare create_task results are
        # GC-vulnerable (the loop holds only weak refs), and shutdown() must
        # be able to stop them before closing the stores they write to.
        self._background_tasks: set[asyncio.Task] = set()

        # Episodic block for the system prompt (time since last talk + recent summaries).
        self.session_context: str = ""
        self._session_msg_count: int = 0

        self.stt_provider: str = settings.stt_provider
        self.model_size: str = settings.whisper_model_size
        self.groq_api_key: str | None = settings.groq_api_key

        # Audio (STT/TTS) is built after boot so first-launch model downloads show progress.
        self.pipeline: AudioPipeline | None = None
        self.speaker: BaseSpeaker | None = None
        self.audio_ready: bool = False
        self.model_status: dict[str, Any] = {
            "ready": False,
            "stage": "starting",
            "progress": 0.0,
            "indeterminate": False,
        }

        # Built in initialize() (needs async); saver kept so reload_tools can rebuild.
        self.graph_app: Any | None = None
        self._conn: aiosqlite.Connection | None = None
        self._saver: AsyncSqliteSaver | None = None

    def _spawn(self, coro: Any) -> asyncio.Task:
        """create_task that keeps a reference and is cancellable by shutdown()."""
        task = asyncio.get_running_loop().create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def initialize(self) -> None:
        """Async one-time initialization: database tables + compiled graph."""
        log.info("engine_initializing")
        await init_db()

        # Load Composio tools before building the graph so bind_tools sees them.
        from yumii.tools.composio_loader import load_and_register_composio_tools

        composio_tools = await load_and_register_composio_tools()
        if composio_tools:
            log.info("composio_ready", count=len(composio_tools))

        # Keep one long-lived connection; from_conn_string() would GC-close it after one turn.
        _CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(_CHECKPOINT_DB))
        self._saver = AsyncSqliteSaver(self._conn)
        self.graph_app = await build_graph(checkpointer=self._saver)
        set_confirmation_hook(self._confirmation_hook)

        # One-time backfill: copy pre-transcript checkpoint history so recall covers it.
        try:
            await self._backfill_transcript_once()
        except Exception:
            log.warning("transcript_backfill_failed", exc_info=True)

        # Continue the last conversation across restarts — the orb's 'auto'
        # reconnect keeps whatever session is active here, so without this a
        # restart silently strands the user in a context-free new chat.
        try:
            await self._restore_last_session()
        except Exception:
            log.warning("session_restore_failed", exc_info=True)

        # Prepare audio in the background so /health and /api/status respond immediately.
        self._spawn(self._prepare_audio())

        log.info("engine_ready")

    async def _prepare_audio(self) -> None:
        """Download models (with progress), build STT+TTS, start the loops; retries on failure."""
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
                self.pipeline = await asyncio.to_thread(self._build_pipeline)
                self.speaker = await asyncio.to_thread(get_speaker)
                self.audio_ready = True
                self.model_status = {
                    "ready": True,
                    "stage": "ready",
                    "progress": 1.0,
                    "indeterminate": False,
                }
                self._spawn(self.audio_listener_task())
                self._spawn(self.reasoning_engine_task())
                self._spawn(self.tts_speaker_task())
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

    def _remember_active_session(self, session_id: str) -> None:
        """Persist the active session so a restart continues this conversation."""
        from yumii.core.global_config import update_global_config

        try:
            update_global_config("LAST_SESSION_ID", session_id)
        except Exception:
            log.warning("last_session_persist_failed", exc_info=True)

    async def _restore_last_session(self) -> None:
        """Make the last active session active again after a restart."""
        from yumii.core.global_config import load_global_config

        if self.active_session_id:
            return
        last_id = load_global_config().get("LAST_SESSION_ID")
        if not last_id:
            return
        session = await session_manager.get_session(last_id)
        if session is None:
            log.info("last_session_missing_starting_fresh", session_id=last_id)
            return
        self.active_session_id = session.id
        self.active_session_name = session.name
        await self._rebuild_session_context(include_current=True)
        log.info("last_session_restored", session_id=session.id, name=session.name)

    async def _backfill_transcript_once(self) -> None:
        """Populate the transcript from checkpoints, first boot only (fresh-upgrade gate)."""
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
                    content = content_to_text(m.content)
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
        """Re-fetch Composio tools and rebuild the graph in place (no restart; history kept)."""
        from yumii.agent.llm import clear_llm_cache
        from yumii.tools.composio_loader import load_and_register_composio_tools

        registered = await load_and_register_composio_tools()
        # Drop the cached tool binding so the next turn binds the new registry.
        clear_llm_cache()
        if self._saver is not None:
            self.graph_app = await build_graph(checkpointer=self._saver)
        log.info("tools_reloaded", composio_count=len(registered))
        return registered

    def _drain_memory_turns(self) -> dict[str, list[dict[str, str]]]:
        """Take the buffered turns, grouped by the session they belong to.

        Turns are tagged at capture time: a turn that finishes after a
        session switch must be reviewed under the session it was spoken in.
        """
        buffered, self._memory_turn_buffer = self._memory_turn_buffer, []
        groups: dict[str, list[dict[str, str]]] = {}
        for sid, entry in buffered:
            groups.setdefault(sid or self.active_session_id or "", []).append(entry)
        return groups

    def _flush_memory_review(self, session_id: str | None = None) -> None:
        """Fire the background memory review over the buffered turns."""
        for sid, turns in self._drain_memory_turns().items():
            self._spawn(memory_manager.review_recent_turns(turns, session_id or sid))

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
        """Summarize an ended session, then refresh the episodic block to include it."""
        from yumii.core.summarizer import summarize_session

        try:
            await summarize_session(session_id)
            await self._rebuild_session_context(include_current=True)
        except Exception:
            log.warning("session_finalize_failed", session_id=session_id, exc_info=True)

    async def shutdown(self) -> None:
        """Clean shutdown: close SQLite connections and memory store."""
        log.info("engine_shutting_down")

        # Review buffered turns before exit (bounded so a slow provider can't
        # hang quit); grouped per session — a stale active id must not
        # capture another session's turns.
        groups = self._drain_memory_turns()
        if groups:
            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        *(
                            memory_manager.review_recent_turns(turns, sid)
                            for sid, turns in groups.items()
                        ),
                        return_exceptions=True,
                    ),
                    timeout=20.0,
                )
            except Exception:
                log.warning("shutdown_memory_review_failed", exc_info=True)

        # Summarize the ending session for next boot's "Recent conversations".
        if self.active_session_id and self._session_msg_count > 0:
            try:
                from yumii.core.summarizer import summarize_session

                await asyncio.wait_for(
                    summarize_session(self.active_session_id), timeout=20.0
                )
            except Exception:
                log.warning("shutdown_session_summary_failed", exc_info=True)

        # Stop the loops and background work BEFORE closing anything they
        # touch — a turn still in flight would otherwise write checkpoints
        # into a closed connection, and pending reviews die with their turns
        # already drained.
        pending = [t for t in self._background_tasks if not t.done()]
        for task in pending:
            task.cancel()
        if pending:
            done, stubborn = await asyncio.wait(pending, timeout=5.0)
            log.info(
                "background_tasks_stopped", stopped=len(done), stubborn=len(stubborn)
            )

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
        """Gate listening without disturbing the loop; drops any half-captured utterance."""
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
        previous_session = self.active_session_id
        self._flush_memory_review()
        await self._clear_all_queues()
        self.interrupt_event.clear()
        # A switch must STOP in-flight speech from the old session — the old
        # clear() here un-cancelled it instead, letting her finish the
        # previous session's reply audibly before speaking in the new one.
        self._cancel_speech()
        self._disarm_speaking_gate()

        session_id = await session_manager.create_session(name)
        self.active_session_id = session_id
        self.active_session_name = name or "New Chat"
        self._session_msg_count = 0
        await self._rebuild_session_context(include_current=False)
        if previous_session:
            self._spawn(self._finalize_session(previous_session))

        facts = await memory_manager.get_facts_raw()
        self._remember_active_session(session_id)
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

        previous_session = self.active_session_id
        self._flush_memory_review()
        await self._clear_all_queues()
        self.interrupt_event.clear()
        self._cancel_speech()  # stop the old session's in-flight speech (see create_new_session)
        self._disarm_speaking_gate()

        self.active_session_id = session.id
        self.active_session_name = session.name
        self._session_msg_count = 0
        await session_manager.update_session_activity(session.id)
        await self._rebuild_session_context(include_current=True)
        if previous_session and previous_session != session.id:
            self._spawn(self._finalize_session(previous_session))

        facts = await memory_manager.get_facts_raw()
        self._remember_active_session(session.id)
        log.info(
            "session_resumed",
            session_id=session.id,
            name=session.name,
            fact_count=len(facts),
        )
        return session.id

    async def _clear_all_queues(self) -> None:
        """Drain all internal queues so no stale audio / text bleeds across sessions.

        The None sentinel afterwards resets any in-flight capture — without
        it, the previous session's half-utterance kept recording and landed
        in the fresh session as its first turn.
        """
        for q in (self.tts_queue, self.transcription_queue, self.audio_input_queue):
            while not q.empty():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    break
        await self.audio_input_queue.put(None)
        log.debug("queues_cleared")

    # ------------------------------------------------------------------
    # Speaking gate: barge-in arming + playback-finished handshake
    # ------------------------------------------------------------------

    def _cancel_speech(self) -> int:
        """Invalidate all speech from earlier generations and return the new one.

        Bumped by every cancel-speech event: barge-in, session switch, and
        the start of a new reasoning turn (a fresh turn takes over the
        airwaves — the queued-speech drain only covered not-yet-played text).
        """
        self._speech_generation += 1
        return self._speech_generation

    def _arm_speaking_gate(self) -> None:
        """While she speaks, interrupting her needs sustained high-confidence speech."""
        self._speak_seq += 1
        self.is_speaking = True
        if self.pipeline is not None:
            self.pipeline.set_speaking_gate(armed=True)

    def _disarm_speaking_gate(self) -> None:
        """Back to normal listening: short trigger, standard VAD threshold."""
        self.is_speaking = False
        if self.pipeline is not None:
            self.pipeline.set_speaking_gate(armed=False)

    def _arm_playback_watchdog(self, seq: int) -> None:
        """Safety net if the webui's playback_finished never arrives."""

        async def _guard() -> None:
            await asyncio.sleep(_PLAYBACK_FINISHED_TIMEOUT_SEC)
            if self._speak_seq == seq and self.is_speaking:
                log.warning("playback_finished_timeout", seq=seq)
                await self.on_playback_finished(seq)

        self._spawn(_guard())

    async def on_playback_finished(self, seq: int | None = None) -> None:
        """Webui reports real playback end — disarm the gate, reset capture.

        The gate must stay armed until actual playback stops, not until the
        last chunk is *sent*; otherwise the mic hears the playback tail and
        self-interrupts (the old is_speaking race). Resetting the capture
        also discards any half-utterance the leaked playback triggered.
        """
        if seq is not None and seq != self._speak_seq:
            return  # a newer speech session is already live
        if not self.is_speaking:
            return
        self._disarm_speaking_gate()
        await self.audio_input_queue.put(None)
        log.debug("playback_finished_disarmed", seq=seq)

    # ------------------------------------------------------------------
    # HITL confirmation gate
    # ------------------------------------------------------------------

    async def _confirmation_hook(
        self,
        request_id: str,
        tool_name: str,
        tool_args: dict,
    ) -> bool:
        """Bridge the gated tools node to the WS layer; a barge-in resolves as deny."""
        # Already interrupted (e.g. "stop") — deny immediately.
        if self.interrupt_event.is_set():
            log.info("confirmation_bypass_interrupt", tool=tool_name)
            return False

        approved = await self.request_confirmation(
            request_id=request_id,
            tool_name=tool_name,
            tool_args=tool_args,
        )

        # Barge-in during the wait also counts as deny.
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
        """Broadcast a confirmation_request and await the reply (False on deny/timeout/barge-in)."""
        if timeout is None:
            timeout = settings.hitl_timeout_seconds

        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        # Register the future BEFORE broadcasting: a fast client replying to
        # the request in the broadcast window must find it, or the approval
        # resolves nothing and hangs until the 30s timeout denies.
        self.pending_confirmations[request_id] = future

        await self.broadcast_payload(
            {
                "type": "confirmation_request",
                "request_id": request_id,
                "tool": tool_name,
                "args": tool_args,
                "timeout_seconds": timeout,
            }
        )

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
        """Resolve a pending confirmation; True if a pending future was found and set."""
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

    async def _handle_text_command(self, text: str) -> bool:
        """Interpret short utterances as direct commands instead of chat.

        Runs for typed input and transcribed speech alike — a spoken "stop"
        or "new chat" works exactly like the typed one. Matching is exact
        after normalization, so ordinary sentences never trip it. Returns
        True when the text was a command and no LLM turn should run.
        """
        normalized = " ".join(text.strip().lower().rstrip(".!?,").split())
        if not normalized:
            return True  # nothing to say — skip the turn

        if normalized in _STOP_PHRASES:
            self._cancel_speech()
            while not self.tts_queue.empty():
                try:
                    self.tts_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            self._disarm_speaking_gate()
            self._spawn(self.broadcast_payload({"type": "interrupt"}))
            log.info("text_command", command="stop")
            return True

        if normalized in _MUTE_PHRASES:
            await self.set_mic_muted(True)
            await self.broadcast_payload({"type": "reply_text", "text": "Mic muted."})
            log.info("text_command", command="mute")
            return True

        if normalized in _UNMUTE_PHRASES:
            await self.set_mic_muted(False)
            await self.broadcast_payload({"type": "reply_text", "text": "Mic unmuted."})
            log.info("text_command", command="unmute")
            return True

        if normalized in _NEW_CHAT_PHRASES:
            await self.create_new_session()
            await self.broadcast_payload(
                {"type": "reply_text", "text": "New chat — I'm all ears."}
            )
            log.info("text_command", command="new chat")
            return True

        if normalized in _REPEAT_PHRASES:
            if self._last_reply_text:
                await self.tts_queue.put(
                    {
                        "kind": "utterance",
                        "gen": self._speech_generation,
                        "response": self._last_reply_text,
                    }
                )
            log.info("text_command", command="repeat")
            return True

        return False

    async def audio_listener_task(self) -> None:
        """Consume audio, trigger interrupts on speech, push transcriptions to the reasoning queue."""

        def on_speech_start() -> None:
            # Barge-in works in both states now: while she speaks, the
            # pipeline's gate only triggers after sustained high-confidence
            # speech (echo through AEC shouldn't survive it). A trigger during
            # playback stops her mid-sentence; the utterance keeps capturing
            # and becomes the next turn.
            was_speaking = self.is_speaking
            if was_speaking:
                log.info("barge_in_accepted")
            else:
                log.debug("speech_started_interrupt")
            self._disarm_speaking_gate()
            self._cancel_speech()
            self.interrupt_event.set()
            self._spawn(self.broadcast_payload({"type": "interrupt"}))

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
                        log.info("transcription_complete", text=transcribed_text)
                        await self.transcription_queue.put(transcribed_text)
                else:
                    audio_segment = await self.pipeline.stream_capture(
                        self.audio_input_queue, on_speech_start
                    )
                    if audio_segment is not None and len(audio_segment) > 0:
                        processed_audio = self.pipeline.process_audio(audio_segment)
                        if len(processed_audio) > 0:
                            # Run STT off the event loop — inference can take seconds.
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
        """Main reasoning loop: stream the graph, broadcast thinking/tool events, then TTS the reply."""
        log.info("reasoning_task_started")
        while True:
            try:
                user_text = await self.transcription_queue.get()

                # Commands (typed or spoken) never become LLM turns.
                if await self._handle_text_command(user_text):
                    continue

                self.interrupt_event.clear()

                while not self.tts_queue.empty():
                    try:
                        self.tts_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                # A new turn takes over the airwaves: bump the generation so
                # any speech still playing from an earlier turn stops at its
                # next chunk check (the drain above only covers not-yet-played
                # text — this is what closes the old interrupt_event race).
                turn_generation = self._cancel_speech()
                # The session this turn belongs to — captured NOW, because a
                # session switch landing mid-turn (or mid-bookkeeping) must
                # not redirect its transcript/summary/memory writes.
                turn_session_id = self.active_session_id
                # One personality read per turn: the synthesizer's per-persona
                # expression calibration needs it for every streamed sentence.
                from yumii.agent.personality_manager import personality_manager

                turn_personality = personality_manager.get_current_personality()

                if not self.active_session_id or not self.graph_app:
                    log.warning("reasoning_skipped_no_session")
                    continue

                log.debug("reasoning_start", user_text=user_text)

                config = {
                    "configurable": {"thread_id": self.active_session_id}
                }

                facts = await memory_manager.get_facts_raw()

                await self.broadcast_payload({"type": "thinking_start"})

                # turn_id scopes message IDs: stable within a turn (dedupe), unique across turns.
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

                # Token→sentence→TTS streaming: a sentence is queued for speech
                # the moment its punctuation closes, while the model keeps
                # generating. The full reply is never waited on.
                segmenter = SentenceSegmenter()
                spoken_sentences: list[str] = []
                stream_open = False
                # Raw tokens streamed during the CURRENT agent pass (reset at
                # each on_chain_end) — a tool pass whose text was already
                # streamed must not be narrated again (the double-speak bug).
                pass_streamed: list[str] = []

                async def _speak_streamed(sentence: str) -> None:
                    """Queue one streamed sentence; the first opens the audio session."""
                    nonlocal stream_open
                    spoken = synthesize(sentence, personality=turn_personality)
                    if not spoken.response_text:
                        return
                    spoken_sentences.append(spoken.response_text)
                    await self.tts_queue.put(
                        {
                            "kind": "stream_text" if stream_open else "stream_start",
                            "response": spoken.response_text,
                            "expression": spoken.expression,
                            "motion": spoken.motion,
                            "gen": self._speech_generation,
                        }
                    )
                    stream_open = True
                    await self.broadcast_payload(
                        {"type": "reply_text", "text": " ".join(spoken_sentences)}
                    )

                try:
                    async for event in self.graph_app.astream_events(
                        initial_state, config=config, version="v2"
                    ):
                        if self._speech_generation != turn_generation:
                            log.info("reasoning_interrupted_mid_stream")
                            break

                        kind = event.get("event")
                        name = event.get("name", "")

                        # Stream tokens as thinking_delta, and split them into
                        # speakable sentences; the graph finalizes the AIMessage itself.
                        if kind == "on_chat_model_stream":
                            # Only the agent node speaks — any other in-graph
                            # model (memory/extraction) must never reach TTS.
                            if event.get("metadata", {}).get("langgraph_node") != "agent":
                                continue
                            chunk = event.get("data", {}).get("chunk")
                            token = getattr(chunk, "content", None) if chunk else None
                            if token:
                                streamed_delta_count += 1
                                await self.broadcast_payload(
                                    {"type": "thinking_delta", "text": token}
                                )
                                if isinstance(token, str):
                                    pass_streamed.append(token)
                                    for sentence in segmenter.feed(token):
                                        await _speak_streamed(sentence)

                        elif kind == "on_tool_start":
                            await self.broadcast_payload(
                                {"type": "tool_status", "tool": name, "status": "running"}
                            )

                        elif kind == "on_tool_end":
                            await self.broadcast_payload(
                                {"type": "tool_status", "tool": name, "status": "done"}
                            )

                        # Capture the agent node's final output for TTS.
                        elif kind == "on_chain_end" and event.get("metadata", {}).get("langgraph_node") == "agent":
                            output = event.get("data", {}).get("output")
                            if isinstance(output, dict) and output.get("response"):
                                reasoning_result = output
                            else:
                                # Tool pass. If this pass streamed text, the
                                # streamer already spoke it sentence-by-sentence
                                # — re-deriving the same pre-tool line here was
                                # the double-speak bug. Only a pass that said
                                # nothing gets a narration line.
                                narration = None
                                if not any(s.strip() for s in pass_streamed):
                                    narration = _derive_tool_narration(
                                        output,
                                        allow_filler=tool_passes_narrated == 0,
                                    )
                                pass_streamed = []
                                if (
                                    narration
                                    and narration != last_narration
                                    and self._speech_generation == turn_generation
                                ):
                                    tool_passes_narrated += 1
                                    last_narration = narration
                                    spoken = synthesize(
                                        narration, personality=turn_personality
                                    )
                                    log.info(
                                        "tool_narration", text=spoken.response_text[:80]
                                    )
                                    await self.tts_queue.put(
                                        {
                                            # While a streamed session is open the
                                            # narration must CONTINUE it (chunk-only):
                                            # a second "utterance" would open a new
                                            # audio session mid-reply, and the webui
                                            # drops the buffered reply tail from then
                                            # on.
                                            "kind": (
                                                "stream_text" if stream_open else "utterance"
                                            ),
                                            "response": spoken.response_text,
                                            "expression": spoken.expression,
                                            "motion": spoken.motion,
                                            "gen": self._speech_generation,
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

                if self._speech_generation != turn_generation:
                    log.info("reasoning_interrupted")
                    continue

                # Close the streamed session: flush any sentence still pending,
                # then hand the speaker task the end-of-audio marker.
                if stream_open:
                    tail = segmenter.flush()
                    if tail:
                        await _speak_streamed(tail)
                    await self.tts_queue.put(
                        {"kind": "stream_end", "gen": self._speech_generation}
                    )

                # Hard failure with nothing to say: show an actionable error card, not a frozen "Thinking".
                if reasoning_result is None and turn_error is not None:
                    kind, message = turn_error
                    log.info("turn_error_surfaced", kind=kind)
                    await self.broadcast_payload(
                        {"type": "error", "kind": kind, "message": message}
                    )
                    continue

                # Stream ended without output: read the checkpoint — NEVER re-invoke (would re-run tools, e.g. double-send).
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

                if reasoning_result.get("response"):
                    self._last_reply_text = reasoning_result["response"]

                log.debug(
                    "reasoning_done",
                    streamed_deltas=streamed_delta_count,
                    response_len=len(reasoning_result.get("response", "")),
                )

                await session_manager.bump_after_turn(
                    turn_session_id, user_text
                )

                # Append to the searchable transcript for future recall.
                try:
                    from yumii.core import transcript

                    await transcript.record_turn(
                        turn_session_id,
                        user_text,
                        reasoning_result["response"],
                    )
                except Exception:
                    log.warning("transcript_record_failed", exc_info=True)

                # Refresh this session's summary periodically so slid-out turns survive in the prompt.
                self._session_msg_count += 2
                from yumii.core.summarizer import SUMMARY_REFRESH_MESSAGES

                if self._session_msg_count % SUMMARY_REFRESH_MESSAGES == 0:
                    self._spawn(self._finalize_session(turn_session_id))
                if self.active_session_name == "New Chat":
                    refreshed = await session_manager.get_session(
                        self.active_session_id
                    )
                    if refreshed:
                        self.active_session_name = refreshed.name

                # Buffer the turn for the periodic memory review — tagged with
                # the session it was spoken in (see _drain_memory_turns).
                self._memory_turn_buffer.extend(
                    (turn_session_id, entry)
                    for entry in (
                        {"role": "user", "content": user_text},
                        {"role": "assistant", "content": reasoning_result["response"]},
                    )
                )
                if len(self._memory_turn_buffer) >= _MEMORY_REVIEW_INTERVAL * 2:
                    self._flush_memory_review()

                if stream_open:
                    # Already spoken sentence-by-sentence; reasoning_result only
                    # feeds the transcript/memory bookkeeping below.
                    pass
                else:
                    await self.tts_queue.put(
                        {
                            "kind": "utterance",
                            "gen": self._speech_generation,
                            **reasoning_result,
                        }
                    )
            except Exception as e:
                log.error("reasoning_engine_crash", error=str(e), exc_info=True)
                await asyncio.sleep(1)

    async def tts_speaker_task(self) -> None:
        """Voice loop: speak queued payloads.

        Payload kinds:
        - ``utterance``: standalone one-shot speech (tool narrations, fallbacks) —
          its own audio_start/audio_end pair.
        - ``stream_start`` / ``stream_text`` / ``stream_end``: one streamed reply
          — a single audio session; sentences flow as audio_chunk on the same
          audio_start, so playback never restarts mid-reply.
        """
        log.info("speaker_task_started")
        while True:
            try:
                payload = await self.tts_queue.get()
                payload_gen = payload.get("gen", self._speech_generation)
                if payload_gen != self._speech_generation:
                    # Speech from a cancelled generation (barge-in, session
                    # switch, newer turn): drop it. The canceller already
                    # disarmed the gate — nothing to do but move on.
                    continue

                kind = payload.get("kind", "utterance")
                response_text = payload.get("response", "")
                expression = payload.get("expression", "normal")
                motion = payload.get("motion", "idle")

                if kind == "stream_end":
                    if self.is_speaking:
                        await self.broadcast_payload({"type": "audio_end"})
                        # Gate stays armed until the webui confirms playback
                        # actually finished (the mic can still hear the tail).
                        self._arm_playback_watchdog(self._speak_seq)
                    continue

                # A dropped stream_start (e.g. interrupt) leaves orphans — skip them.
                if kind == "stream_text" and not self.is_speaking:
                    continue

                if kind in ("stream_start", "utterance"):
                    self._arm_speaking_gate()
                    log.info("yumii_response", text=response_text)

                if not response_text or not response_text.strip():
                    if kind == "utterance":
                        self._disarm_speaking_gate()
                    continue

                if hasattr(self.speaker, "stream_speak"):
                    # Only a session opener (or standalone utterance) may send
                    # audio_start/audio_end; streamed continuations are chunk-only.
                    first = kind in ("stream_start", "utterance")
                    interrupted = False
                    try:
                        # aclosing: on barge-in break, the generator's finally
                        # runs and cancels the prefetch worker mid-synthesis.
                        async with aclosing(
                            self.speaker.stream_speak(response_text)
                        ) as stream:
                            async for chunk_data in stream:
                                if payload_gen != self._speech_generation:
                                    interrupted = True
                                    break

                                # Only a session opener announces audio_start;
                                # continuations skip their metadata and reuse
                                # the already-open session.
                                if (
                                    isinstance(chunk_data, dict)
                                    and chunk_data.get("type") == "metadata"
                                ):
                                    if first:
                                        await self.broadcast_payload(
                                            {
                                                "type": "audio_start",
                                                "sampleRate": chunk_data["sampleRate"],
                                                "text": response_text,
                                                "expression": expression,
                                                "motion": motion,
                                                "seq": self._speak_seq,
                                            }
                                        )
                                else:
                                    await self.broadcast_payload(
                                        {"type": "audio_chunk", "data": chunk_data}
                                    )
                    except Exception as stream_err:
                        log.error("tts_stream_error", error=str(stream_err), exc_info=True)
                        if first:
                            await self.broadcast_payload(
                                {
                                    "text": response_text,
                                    "expression": expression,
                                    "motion": motion,
                                    "audio": None,
                                    "error": f"TTS failed: {stream_err}",
                                }
                            )
                            self._disarm_speaking_gate()
                        continue

                    if interrupted:
                        self._disarm_speaking_gate()
                        continue

                    if kind == "utterance":
                        await self.broadcast_payload({"type": "audio_end"})
                        self._arm_playback_watchdog(self._speak_seq)
                    # stream_start / stream_text: gate stays armed until the
                    # webui's playback_finished (or stream_end's watchdog).
                else:
                    # Non-streaming provider: every payload speaks standalone (legacy).
                    if kind == "stream_end":
                        continue
                    audio_b64, duration = await asyncio.to_thread(
                        self.speaker.speak, response_text
                    )
                    self._disarm_speaking_gate()
                    if payload_gen != self._speech_generation:
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
                            if payload_gen != self._speech_generation:
                                break
                            await asyncio.sleep(0.1)
                            slept += 0.1

            except Exception as e:
                log.error("tts_speaker_crash", error=str(e), exc_info=True)
                await asyncio.sleep(1)
