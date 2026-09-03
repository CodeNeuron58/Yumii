"""Tests for the speaking gate: barge-in arming and the playback-finished handshake."""

import asyncio

import pytest

from yumii.audio.stt import (
    BARGE_IN_TRIGGER_FRAMES,
    SILERO_BARGE_THRESHOLD,
    SILENCE_END_FRAMES,
    SILERO_THRESHOLD,
    SPEECH_TRIGGER_FRAMES,
    AudioPipeline,
)
from yumii.core.engine import YumiiEngine


def test_speaking_gate_switches_pipeline_params():
    p = object.__new__(AudioPipeline)  # skip model loading
    p.speech_trigger_frames = SPEECH_TRIGGER_FRAMES
    p.speech_threshold = SILERO_THRESHOLD

    p.set_speaking_gate(armed=True)
    assert p.speech_trigger_frames == BARGE_IN_TRIGGER_FRAMES
    assert p.speech_threshold == SILERO_BARGE_THRESHOLD

    p.set_speaking_gate(armed=False)
    assert p.speech_trigger_frames == SPEECH_TRIGGER_FRAMES
    assert p.speech_threshold == SILERO_THRESHOLD


def test_barge_in_gate_is_stricter_than_normal():
    assert BARGE_IN_TRIGGER_FRAMES > SPEECH_TRIGGER_FRAMES
    assert SILERO_BARGE_THRESHOLD > SILERO_THRESHOLD
    # and the silence-end budget is untouched by the gate
    assert SILENCE_END_FRAMES == 12


def _engine() -> YumiiEngine:
    e = object.__new__(YumiiEngine)  # skip __init__ wiring
    e.interrupt_event = asyncio.Event()
    e.audio_input_queue = asyncio.Queue()
    e.is_speaking = False
    e._speak_seq = 0
    e.pipeline = None
    return e


@pytest.mark.asyncio
async def test_playback_finished_disarms_and_resets_capture():
    e = _engine()
    e._speak_seq = 3
    e.is_speaking = True

    await e.on_playback_finished(3)

    assert not e.is_speaking
    # None sentinel pushed so any echo-triggered half-capture is discarded
    assert e.audio_input_queue.qsize() == 1
    assert e.audio_input_queue.get_nowait() is None


@pytest.mark.asyncio
async def test_stale_playback_finished_is_ignored():
    e = _engine()
    e._speak_seq = 5
    e.is_speaking = True

    await e.on_playback_finished(4)  # report from the previous session

    assert e.is_speaking  # the newer session is still live
    assert e.audio_input_queue.empty()


@pytest.mark.asyncio
async def test_playback_finished_when_idle_is_noop():
    e = _engine()
    await e.on_playback_finished(0)
    assert not e.is_speaking
    assert e.audio_input_queue.empty()


@pytest.mark.asyncio
async def test_arm_increments_session_seq():
    e = _engine()
    e._arm_speaking_gate()
    assert e.is_speaking
    assert e._speak_seq == 1
    e._arm_speaking_gate()
    assert e._speak_seq == 2
    e._disarm_speaking_gate()
    assert not e.is_speaking
