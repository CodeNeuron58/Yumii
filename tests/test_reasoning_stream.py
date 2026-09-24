"""The reasoning loop's speech contract: streamed sessions, tool narration,
and generation-based cancellation.

Drives ``reasoning_engine_task`` with a fake graph and stubbed singletons —
the same harness style as test_speaking_gate.py. Regressions covered here:
- a tool pass whose text was already streamed must not be narrated again
  (the double-speak bug);
- narration during an open stream must CONTINUE it, not open a second
  audio session (the webui dropped the reply tail from then on);
- block-list message content must never reach TTS as repr gibberish;
- a generation bump mid-stream aborts the turn.
"""

import asyncio
from types import SimpleNamespace

import pytest

from yumii.core import transcript
from yumii.core.engine import YumiiEngine
from yumii.core.memory_manager import memory_manager
from yumii.core.session_manager import session_manager
from langchain_core.messages import AIMessage


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


class _FakeGraph:
    """astream_events that yields canned events (v2 shape, agent node only).

    ``mid_stream_hook`` runs after an event has been processed, just before
    the next one is delivered — the window where a barge-in would land.
    """

    def __init__(self, events, mid_stream_hook=None) -> None:
        self._events = events
        self._hook = mid_stream_hook

    async def astream_events(self, state, config=None, version=None):
        for ev in self._events:
            yield ev
            if self._hook is not None:
                self._hook()
                self._hook = None


def _token(text: str) -> dict:
    return {
        "event": "on_chat_model_stream",
        "name": "ChatOpenAI",
        "metadata": {"langgraph_node": "agent"},
        "data": {"chunk": SimpleNamespace(content=text)},
    }


def _tool_pass(content, with_tool_calls: bool = True) -> dict:
    msg = AIMessage(
        content=content,
        tool_calls=[{"name": "web_search", "args": {}, "id": "c1"}]
        if with_tool_calls
        else [],
    )
    return {
        "event": "on_chain_end",
        "name": "ChatOpenAI",
        "metadata": {"langgraph_node": "agent"},
        "data": {"output": {"messages": [msg], "input": "hi"}},
    }


def _final_pass(response_text: str) -> dict:
    return {
        "event": "on_chain_end",
        "name": "ChatOpenAI",
        "metadata": {"langgraph_node": "agent"},
        "data": {
            "output": {
                "messages": [AIMessage(content=response_text)],
                "response": response_text,
                "expression": "smile",
                "motion": "nod",
            }
        },
    }


def _reasoning_engine(events, mid_stream_hook=None) -> tuple[YumiiEngine, list, list]:
    """Engine stub wired for reasoning_engine_task; returns (engine, tts payloads, broadcasts)."""
    e = object.__new__(YumiiEngine)
    e.transcription_queue = asyncio.Queue()
    e.tts_queue = asyncio.Queue()
    e.interrupt_event = asyncio.Event()
    e._speech_generation = 0
    e.is_speaking = False
    e._speak_seq = 0
    e.pipeline = None
    e.audio_input_queue = asyncio.Queue()
    e.mic_muted = False
    e._background_tasks = set()
    e._last_reply_text = None
    e.active_session_id = "sess-1"
    e.active_session_name = "Test"  # not "New Chat" — skips the name refresh
    e.session_context = ""
    e._session_msg_count = 0
    e._memory_turn_buffer = []
    e.graph_app = _FakeGraph(events, mid_stream_hook)

    sent: list = []
    tts: list = []

    async def fake_broadcast(payload):
        sent.append(payload)

    async def fake_get_facts_raw():
        return []

    async def fake_bump(session_id, user_text):
        return None

    async def fake_record_turn(session_id, user_text, reply):
        return 1

    async def fake_finalize(session_id):
        return None

    e.broadcast_payload = fake_broadcast
    e._finalize_session = fake_finalize

    orig_tts_put = e.tts_queue.put

    async def tts_put(item):
        tts.append(item)
        await orig_tts_put(item)

    e.tts_queue.put = tts_put
    return e, tts, sent


async def _run_turn(e: YumiiEngine) -> None:
    """Put one user text and drive the loop until the turn completes."""
    await e.transcription_queue.put("hello yumii")
    task = asyncio.create_task(e.reasoning_engine_task())
    try:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 5.0
        while not any(p.get("type") == "thinking_end" for p in e._sent_broadcasts):
            if loop.time() > deadline:
                raise TimeoutError("reasoning turn never completed")
            await asyncio.sleep(0.01)
        # let the post-stream bookkeeping run to completion
        await asyncio.sleep(0.05)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.fixture
def stubbed_singletons(monkeypatch):
    """Silence the engine's collaborators and record their session-id calls."""
    from yumii.core.summarizer import SUMMARY_REFRESH_MESSAGES

    calls: dict[str, list] = {"bump": [], "record": []}

    async def no_facts():
        return []

    async def fake_bump(session_id, user_text):
        calls["bump"].append((session_id, user_text))

    async def fake_record_turn(session_id, user_text, reply):
        calls["record"].append((session_id, user_text, reply))

    monkeypatch.setattr(memory_manager, "get_facts_raw", no_facts)
    monkeypatch.setattr(session_manager, "bump_after_turn", fake_bump)
    monkeypatch.setattr(transcript, "record_turn", fake_record_turn)
    # Keep the periodic-summary trigger from firing _finalize_session for real.
    assert SUMMARY_REFRESH_MESSAGES > 2  # one turn must never hit the refresh
    return calls


# ---------------------------------------------------------------------------
# Streamed replies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streamed_reply_queues_session_and_skips_final_utterance(
    stubbed_singletons,
):
    """With a streamed session open, the final reasoning_result must NOT be
    queued as a second utterance — everything was already spoken."""
    e, tts, sent = _reasoning_engine(
        [_token("Hello there. "), _final_pass("Hello there.")]
    )
    e._sent_broadcasts = sent
    await _run_turn(e)

    assert [p["kind"] for p in tts] == ["stream_start", "stream_end"]
    assert tts[0]["response"] == "Hello there."


@pytest.mark.asyncio
async def test_payloads_carry_the_turn_generation(stubbed_singletons):
    e, tts, sent = _reasoning_engine(
        [_token("Hi. "), _final_pass("Hi.")]
    )
    e._sent_broadcasts = sent
    await _run_turn(e)

    assert e._speech_generation == 1  # the turn bumped it exactly once
    assert all(p["gen"] == 1 for p in tts)


# ---------------------------------------------------------------------------
# Tool narration: no double-speak, no second audio session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streamed_tool_pass_is_not_narrated_twice(stubbed_singletons):
    """The model's pre-tool line was already streamed sentence-by-sentence;
    re-speaking it as tool narration was the double-speak bug."""
    e, tts, sent = _reasoning_engine(
        [
            _token("Sure thing. Let me check the weather. "),
            _tool_pass("Sure thing. Let me check the weather."),
            _token("It is sunny today. "),
            _final_pass("It is sunny today."),
        ]
    )
    e._sent_broadcasts = sent
    await _run_turn(e)

    kinds = [p["kind"] for p in tts]
    # exactly one speech payload per sentence, one stream_end — no "utterance"
    assert kinds == ["stream_start", "stream_text", "stream_text", "stream_end"]
    # and no sentence was spoken twice
    responses = [p["response"] for p in tts if "response" in p]
    assert len(responses) == len(set(responses))


@pytest.mark.asyncio
async def test_narration_during_open_stream_continues_it(stubbed_singletons):
    """A provider whose tokens never arrive as str (block content): pass 1
    streams normally, its content matches (no re-narration), and a later
    pass with unsreamed block-text gets narrated as a stream_text
    CONTINUATION — never a second audio session mid-reply (the webui's
    audio_start handler stops all audio and dropped the reply tail)."""
    e, tts, sent = _reasoning_engine(
        [
            _token("Sure thing. "),
            _tool_pass("Sure thing."),  # streamed text → no re-narration
            _tool_pass([{"type": "text", "text": "One moment."}]),
            _token("It is sunny today. "),
            _final_pass("It is sunny today."),
        ]
    )
    e._sent_broadcasts = sent
    await _run_turn(e)

    kinds = [p["kind"] for p in tts]
    assert kinds == ["stream_start", "stream_text", "stream_text", "stream_end"]
    assert tts[1]["response"] == "One moment."


@pytest.mark.asyncio
async def test_silent_tool_pass_before_any_stream_opens_standalone_session(
    stubbed_singletons,
):
    """No stream open yet → the filler is a standalone utterance (unchanged
    pre-existing behavior)."""
    e, tts, sent = _reasoning_engine(
        [
            _tool_pass(""),
            _token("It is sunny today. "),
            _final_pass("It is sunny today."),
        ]
    )
    e._sent_broadcasts = sent
    await _run_turn(e)

    kinds = [p["kind"] for p in tts]
    # filler is a standalone utterance; the reply then opens its own stream
    # session (one sentence → stream_start, no continuation payload)
    assert kinds == ["utterance", "stream_start", "stream_end"]


# ---------------------------------------------------------------------------
# Block-list content and cancellation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_block_list_content_is_not_repr_spoken(stubbed_singletons):
    """Tokens that never arrive as str (block-content provider) must still be
    narrated from the final content — flattened, never as repr gibberish."""
    e, tts, sent = _reasoning_engine(
        [
            _tool_pass([{"type": "text", "text": "Let me check the weather."}]),
            _token("It is sunny today. "),
            _final_pass("It is sunny today."),
        ]
    )
    e._sent_broadcasts = sent
    await _run_turn(e)

    assert tts[0]["kind"] == "utterance"
    assert tts[0]["response"] == "Let me check the weather."
    assert "'type'" not in tts[0]["response"]


@pytest.mark.asyncio
async def test_generation_bump_mid_stream_aborts_the_turn(stubbed_singletons):
    """A cancellation landing mid-stream (barge-in / session switch / newer
    turn) stops event processing immediately — no further tokens, no speech
    queued after the bump."""

    def hook():
        e._speech_generation += 1  # fires after the first event is processed

    e, tts, sent = _reasoning_engine(
        [
            _token("First. "),
            _token("Second. "),
            _final_pass("never reached"),
        ],
        mid_stream_hook=hook,
    )
    e._sent_broadcasts = sent
    await _run_turn(e)

    deltas = [p["text"] for p in sent if p["type"] == "thinking_delta"]
    assert deltas == ["First. "]  # the second token was never processed
    # the pre-bump sentence is queued but tagged with the now-stale generation
    assert len(tts) == 1
    assert tts[0]["gen"] != e._speech_generation


@pytest.mark.asyncio
async def test_turn_bookkeeping_uses_the_session_captured_at_turn_start(
    stubbed_singletons,
):
    """A session switch landing mid-turn must not redirect the turn's
    transcript/memory writes into the new session. (A real switch also bumps
    the speech generation and aborts the turn; this pins the bookkeeping
    capture for the interleaving windows where it doesn't.)"""

    def switch_session():
        e.active_session_id = "sess-2"  # resume_session lands here

    e, tts, sent = _reasoning_engine(
        [_token("First. "), _final_pass("First. reply")],
        mid_stream_hook=switch_session,
    )
    e._sent_broadcasts = sent
    await _run_turn(e)

    assert stubbed_singletons["bump"][0][0] == "sess-1"
    assert stubbed_singletons["record"][0][0] == "sess-1"
    assert all(sid == "sess-1" for sid, _ in e._memory_turn_buffer)


# ── Text command channel (typed or spoken) ─────────────────────────────


def _command_engine():
    """Engine stub for _handle_text_command; returns (engine, sent, muted, created)."""
    e = object.__new__(YumiiEngine)
    e.transcription_queue = asyncio.Queue()
    e.tts_queue = asyncio.Queue()
    e.audio_input_queue = asyncio.Queue()
    e.interrupt_event = asyncio.Event()
    e._speech_generation = 0
    e._speak_seq = 0
    e.is_speaking = False
    e.pipeline = None
    e.mic_muted = False
    e._background_tasks = set()
    e._memory_turn_buffer = []
    e._last_reply_text = "the previous reply"
    e.active_session_id = "sess-1"
    e.active_session_name = "Test"
    e._session_msg_count = 0

    sent: list = []

    async def fake_broadcast(payload):
        sent.append(payload)

    e.broadcast_payload = fake_broadcast
    muted: list = []

    async def fake_mute(value):
        muted.append(value)

    e.set_mic_muted = fake_mute
    created: list = []

    async def fake_new_session(name=None):
        created.append(name)
        return "s-new"

    e.create_new_session = fake_new_session
    return e, sent, muted, created


@pytest.mark.asyncio
async def test_typed_stop_cancels_speech_and_skips_the_turn():
    e, sent, _, _ = _command_engine()
    e.tts_queue.put_nowait(
        {"kind": "utterance", "gen": e._speech_generation, "response": "old"}
    )

    handled = await e._handle_text_command("Stop!")

    assert handled
    assert e.tts_queue.empty()        # queued speech dropped
    assert e._speech_generation == 1  # generation bumped → in-flight speech stops
    await asyncio.sleep(0)            # let the spawned broadcast task run
    assert any(p["type"] == "interrupt" for p in sent)


@pytest.mark.asyncio
async def test_typed_mute_unmute_and_new_chat():
    e, sent, muted, created = _command_engine()

    assert await e._handle_text_command("mute yourself.")
    assert muted == [True]
    assert any(p["type"] == "reply_text" and p["text"] == "Mic muted." for p in sent)

    assert await e._handle_text_command("unmute")
    assert muted == [True, False]

    assert await e._handle_text_command("new chat")
    assert created == [None]
    assert any("New chat" in p["text"] for p in sent if p["type"] == "reply_text")


@pytest.mark.asyncio
async def test_typed_repeat_requeues_the_last_reply():
    e, sent, _, _ = _command_engine()

    handled = await e._handle_text_command("say that again")

    assert handled
    assert [p["response"] for p in e.tts_queue._queue if isinstance(p, dict)] == [
        "the previous reply"
    ]


@pytest.mark.asyncio
async def test_empty_text_is_swallowed():
    e, _, _, _ = _command_engine()
    assert await e._handle_text_command("   ")


@pytest.mark.asyncio
async def test_normal_sentences_are_not_commands():
    e, _, _, _ = _command_engine()
    for text in (
        "stop making that joke",
        "can you mute the tv",
        "what's a new chat?",
        "please repeat the chorus",
    ):
        assert not await e._handle_text_command(text)


@pytest.mark.asyncio
async def test_stop_command_never_reaches_the_graph(stubbed_singletons):
    """A typed/spoken 'stop' must not produce an LLM turn."""
    e, tts, sent = _reasoning_engine([_token("should never run")])
    e._sent_broadcasts = sent
    await e.transcription_queue.put("stop")

    task = asyncio.create_task(e.reasoning_engine_task())
    try:
        await asyncio.sleep(0.15)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert not any(p["type"] == "thinking_start" for p in sent)
    assert tts == []
