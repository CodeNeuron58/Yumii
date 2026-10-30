"""Answering a tool approval by voice, and the island's other engine hooks.

The island says "say yes or no": an exact yes/no phrase resolves a pending
approval, anything else denies it and becomes the next turn, and a bare
speech onset (a cough) no longer denies it on the spot.
"""

import asyncio
import json

import pytest

from yumii.core.engine import YumiiEngine, _approval_answer, _tool_result_event


def _engine() -> tuple[YumiiEngine, list]:
    e = object.__new__(YumiiEngine)  # skip __init__ wiring
    e.interrupt_event = asyncio.Event()
    e._speech_generation = 0
    e.audio_input_queue = asyncio.Queue()
    e.transcription_queue = asyncio.Queue()
    e.tts_queue = asyncio.Queue()
    e.is_speaking = False
    e._speak_seq = 0
    e.pipeline = None
    e.mic_muted = False
    e.pending_confirmations = {}
    e._background_tasks = set()
    e._maybe_warm_llm = lambda: None
    sent: list = []

    async def fake_broadcast(payload):
        sent.append(payload)

    e.broadcast_payload = fake_broadcast
    return e, sent


def _pending(e: YumiiEngine, request_id: str = "r1") -> asyncio.Future:
    future = asyncio.get_running_loop().create_future()
    e.pending_confirmations[request_id] = future
    return future


# ── The phrase classifier ──────────────────────────────────────────────


@pytest.mark.parametrize("text", ["Yes.", "yes please", "Okay!", "Send it.", "go ahead", "Yeah"])
def test_yes_phrases_approve(text):
    assert _approval_answer(text) is True


@pytest.mark.parametrize("text", ["No.", "nope", "Cancel", "Don't send.", "never mind", "Stop!"])
def test_no_phrases_deny(text):
    assert _approval_answer(text) is False


@pytest.mark.parametrize(
    "text",
    ["Yes, but change the subject", "what's the weather", "no wait I meant Tuesday", ""],
)
def test_anything_else_is_not_an_answer(text):
    """Only exact phrases count — a misheard sentence must never approve."""
    assert _approval_answer(text) is None


# ── Routing utterances while an approval waits ─────────────────────────


@pytest.mark.asyncio
async def test_spoken_yes_approves_and_is_consumed():
    e, sent = _engine()
    future = _pending(e)

    await e.deliver_utterance("Yes, please.")

    assert future.result() is True
    assert e.transcription_queue.empty()  # not a new turn
    assert {"type": "confirmation_resolved", "request_id": "r1", "approved": True} in sent


@pytest.mark.asyncio
async def test_spoken_no_denies_and_is_consumed():
    e, sent = _engine()
    future = _pending(e)

    await e.deliver_utterance("nope")

    assert future.result() is False
    assert e.transcription_queue.empty()


@pytest.mark.asyncio
async def test_other_speech_denies_and_becomes_the_next_turn():
    e, sent = _engine()
    future = _pending(e)

    await e.deliver_utterance("actually, what's the weather in Tokyo")

    assert future.result() is False
    assert e.transcription_queue.get_nowait() == "actually, what's the weather in Tokyo"


@pytest.mark.asyncio
async def test_without_a_pending_approval_yes_is_just_speech():
    e, sent = _engine()

    await e.deliver_utterance("yes")

    assert e.transcription_queue.get_nowait() == "yes"
    assert sent == []


# ── Speech onset ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_speech_onset_leaves_a_pending_approval_open():
    """The old behaviour denied it on any onset — so saying "yes" said no."""
    e, sent = _engine()
    future = _pending(e)

    e._on_speech_start()
    await asyncio.sleep(0)

    assert not future.done()
    assert not e.interrupt_event.is_set()  # the gate would veto an approval
    assert e._speech_generation == 1       # her narration still stops


@pytest.mark.asyncio
async def test_speech_onset_without_an_approval_interrupts():
    e, sent = _engine()

    e._on_speech_start()
    await asyncio.sleep(0)

    assert e.interrupt_event.is_set()
    assert {"type": "interrupt"} in sent


# ── Replay, mute sync, tool results ────────────────────────────────────


@pytest.mark.asyncio
async def test_replay_queues_speech_on_a_fresh_generation():
    e, sent = _engine()
    await e.tts_queue.put({"kind": "utterance", "gen": 0, "response": "old"})

    await e.speak_text("  Design review at 2:30.  ")

    payload = e.tts_queue.get_nowait()
    assert payload == {"kind": "utterance", "gen": 1, "response": "Design review at 2:30."}
    assert e.tts_queue.empty()


@pytest.mark.asyncio
async def test_replay_of_nothing_says_nothing():
    e, sent = _engine()
    await e.speak_text("   ")
    assert e.tts_queue.empty()


@pytest.mark.asyncio
async def test_mute_change_is_broadcast_to_the_island():
    e, sent = _engine()

    await e.set_mic_muted(True)

    assert {"type": "mic_state", "muted": True} in sent


def test_inbox_read_reports_what_it_read():
    output = json.dumps(
        {
            "successful": True,
            "data": {
                "messages": [
                    {"sender": "Priya Shah <priya@example.com>", "subject": "Q4 deck", "messageTimestamp": "2026-10-30T09:04:00Z"},
                    {"sender": "Airline", "subject": "Check-in opens tonight"},
                ]
            },
        }
    )

    event = _tool_result_event("GMAIL_FETCH_EMAILS", output)

    assert event["ok"] is True
    assert event["emails"][0] == {"from": "Priya Shah", "subject": "Q4 deck", "time": "2026-10-30T09:04:00Z"}
    assert event["emails"][1]["from"] == "Airline"


def test_failed_composio_call_reports_not_ok():
    event = _tool_result_event("GMAIL_SEND_EMAIL", json.dumps({"successful": False, "error": "x"}))
    assert event["ok"] is False
    assert "emails" not in event


def test_plain_text_result_claims_nothing():
    """A tool that doesn't report success must not be shown as done."""
    event = _tool_result_event("web_search", "Top web results for ...")
    assert event == {"type": "tool_result", "tool": "web_search", "ok": None}
