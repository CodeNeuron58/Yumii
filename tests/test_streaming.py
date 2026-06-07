"""Tests for the streaming event wiring in YumiiEngine.reasoning_engine_task.

These tests use mocks for the LangGraph app and WebSocket broadcast so
the test stays a pure unit test of the engine's event-emission logic.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from yumii.core.engine import YumiiEngine


def _make_fake_graph_app(events: List[Dict[str, Any]], final_state: Dict[str, Any]):
    """Build a mock LangGraph app whose ``astream_events`` yields the
    given events and whose ``ainvoke`` returns ``final_state``.

    The fake also exposes a ``graph_app.ainvoke`` so the fallback path
    in the engine still works.
    """

    async def astream_events(initial, config=None, version=None):
        for ev in events:
            yield ev

    async def ainvoke(initial, config=None):
        return final_state

    app = MagicMock()
    app.astream_events = astream_events
    app.ainvoke = ainvoke
    return app


@pytest.mark.asyncio
async def test_reasoning_engine_emits_thinking_start_and_end(monkeypatch) -> None:
    """The engine should broadcast ``thinking_start`` then ``thinking_end``."""
    engine = YumiiEngine.__new__(YumiiEngine)
    engine.transcription_queue: asyncio.Queue[str] = asyncio.Queue()
    engine.tts_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
    engine.audio_input_queue: asyncio.Queue[bytes] = asyncio.Queue()
    engine.interrupt_event = asyncio.Event()
    engine.active_connections: list = []
    engine.is_speaking = False
    engine.active_session_id = "s1"
    engine.active_session_name = "Test"

    # Pre-load a transcription
    await engine.transcription_queue.put("hello there")

    # Capture broadcast payloads
    sent: list[dict] = []
    engine.broadcast_payload = AsyncMock(side_effect=lambda p: sent.append(p))

    # Patch memory and session activity side effects
    monkeypatch.setattr(
        "yumii.core.engine.memory_manager",
        MagicMock(
            get_facts_raw=AsyncMock(return_value=[]),
            extract_facts_from_messages=AsyncMock(return_value=None),
        ),
    )
    monkeypatch.setattr(
        "yumii.core.engine.session_manager",
        MagicMock(update_session_activity=AsyncMock(return_value=None)),
    )

    # A fake graph that emits a few events and returns a final state
    fake_graph = _make_fake_graph_app(
        events=[],
        final_state={"response": "the sky is blue", "expression": "normal", "motion": "idle"},
    )
    engine.graph_app = fake_graph

    # Run one iteration of the reasoning loop, then break out
    task = asyncio.create_task(engine.reasoning_engine_task())
    # Wait for it to drain the queue
    tts_payload = await asyncio.wait_for(engine.tts_queue.get(), timeout=5.0)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    types = [p.get("type") for p in sent]
    assert "thinking_start" in types
    assert "thinking_end" in types
    # The TTS payload should be the synthesized YumiiResponse
    assert tts_payload["response"] == "the sky is blue"


@pytest.mark.asyncio
async def test_reasoning_engine_emits_tool_status(monkeypatch) -> None:
    """on_tool_start should produce a ``tool_status`` broadcast."""
    engine = YumiiEngine.__new__(YumiiEngine)
    engine.transcription_queue = asyncio.Queue()
    engine.tts_queue = asyncio.Queue()
    engine.audio_input_queue = asyncio.Queue()
    engine.interrupt_event = asyncio.Event()
    engine.active_connections = []
    engine.is_speaking = False
    engine.active_session_id = "s1"
    engine.active_session_name = "Test"
    await engine.transcription_queue.put("what time is it?")

    sent: list[dict] = []
    engine.broadcast_payload = AsyncMock(side_effect=lambda p: sent.append(p))

    monkeypatch.setattr(
        "yumii.core.engine.memory_manager",
        MagicMock(
            get_facts_raw=AsyncMock(return_value=[]),
            extract_facts_from_messages=AsyncMock(return_value=None),
        ),
    )
    monkeypatch.setattr(
        "yumii.core.engine.session_manager",
        MagicMock(update_session_activity=AsyncMock(return_value=None)),
    )

    fake_graph = _make_fake_graph_app(
        events=[
            {
                "event": "on_tool_start",
                "name": "get_current_time",
                "data": {},
                "metadata": {},
            },
            {
                "event": "on_tool_end",
                "name": "get_current_time",
                "data": {},
                "metadata": {},
            },
        ],
        final_state={"response": "the time is noon", "expression": "normal", "motion": "idle"},
    )
    engine.graph_app = fake_graph

    task = asyncio.create_task(engine.reasoning_engine_task())
    await asyncio.wait_for(engine.tts_queue.get(), timeout=2.0)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    tool_running = [p for p in sent if p.get("type") == "tool_status" and p.get("status") == "running"]
    tool_done = [p for p in sent if p.get("type") == "tool_status" and p.get("status") == "done"]
    assert len(tool_running) == 1
    assert tool_running[0]["tool"] == "get_current_time"
    assert len(tool_done) == 1


@pytest.mark.asyncio
async def test_reasoning_engine_falls_back_to_ainvoke_on_no_streamed_output(monkeypatch) -> None:
    """If astream_events emits no agent output, fall back to ainvoke."""
    engine = YumiiEngine.__new__(YumiiEngine)
    engine.transcription_queue = asyncio.Queue()
    engine.tts_queue = asyncio.Queue()
    engine.audio_input_queue = asyncio.Queue()
    engine.interrupt_event = asyncio.Event()
    engine.active_connections = []
    engine.is_speaking = False
    engine.active_session_id = "s1"
    engine.active_session_name = "Test"
    await engine.transcription_queue.put("hi")

    sent: list[dict] = []
    engine.broadcast_payload = AsyncMock(side_effect=lambda p: sent.append(p))

    monkeypatch.setattr(
        "yumii.core.engine.memory_manager",
        MagicMock(
            get_facts_raw=AsyncMock(return_value=[]),
            extract_facts_from_messages=AsyncMock(return_value=None),
        ),
    )
    monkeypatch.setattr(
        "yumii.core.engine.session_manager",
        MagicMock(update_session_activity=AsyncMock(return_value=None)),
    )

    # Graph that emits NO agent output but ainvoke returns a real value
    fake_graph = _make_fake_graph_app(
        events=[{"event": "on_chain_start", "name": "agent", "data": {}, "metadata": {}}],
        final_state={"response": "fallback response", "expression": "normal", "motion": "idle"},
    )
    engine.graph_app = fake_graph

    task = asyncio.create_task(engine.reasoning_engine_task())
    payload = await asyncio.wait_for(engine.tts_queue.get(), timeout=2.0)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert payload["response"] == "fallback response"


@pytest.mark.asyncio
async def test_reasoning_engine_interrupt_during_stream_drops_tts(monkeypatch) -> None:
    """If ``interrupt_event`` is set mid-stream, the TTS payload is NOT queued."""
    engine = YumiiEngine.__new__(YumiiEngine)
    engine.transcription_queue = asyncio.Queue()
    engine.tts_queue = asyncio.Queue()
    engine.audio_input_queue = asyncio.Queue()
    engine.interrupt_event = asyncio.Event()
    engine.active_connections = []
    engine.is_speaking = False
    engine.active_session_id = "s1"
    engine.active_session_name = "Test"
    await engine.transcription_queue.put("hi")

    engine.broadcast_payload = AsyncMock()

    monkeypatch.setattr(
        "yumii.core.engine.memory_manager",
        MagicMock(
            get_facts_raw=AsyncMock(return_value=[]),
            extract_facts_from_messages=AsyncMock(return_value=None),
        ),
    )
    monkeypatch.setattr(
        "yumii.core.engine.session_manager",
        MagicMock(update_session_activity=AsyncMock(return_value=None)),
    )

    async def stream_with_interrupt(initial, config=None, version=None):
        # Simulate the user interrupting mid-stream
        engine.interrupt_event.set()
        yield {"event": "on_chat_model_stream", "name": "agent", "data": {"chunk": MagicMock(content="x")}, "metadata": {}}

    fake_graph = MagicMock()
    fake_graph.astream_events = stream_with_interrupt
    fake_graph.ainvoke = AsyncMock(return_value={"response": "ignored"})
    engine.graph_app = fake_graph

    task = asyncio.create_task(engine.reasoning_engine_task())
    # Allow a brief moment for the loop to run
    await asyncio.sleep(0.2)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # The tts_queue should still be empty because the interrupt fired
    # before the final state was produced.
    assert engine.tts_queue.empty()
