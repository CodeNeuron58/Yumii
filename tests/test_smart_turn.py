"""Tests for Smart Turn end-of-turn detection and its wiring into the capture loops."""

import asyncio

import numpy as np
import pytest

from yumii.audio.smart_turn import (
    SmartTurn,
    get_smart_turn,
    truncate_or_pad_to_last_n_seconds,
)
from yumii.audio.stt import (
    FRAME_SIZE,
    SILENCE_END_FRAMES,
    SILENCE_END_FRAMES_QUICK,
    SMART_TURN_RECHECK_STRIDE,
    SPEECH_TRIGGER_FRAMES,
    SILERO_THRESHOLD,
    AudioPipeline,
)

# ---------------------------------------------------------------------------
# Pure helper: 8-second tail window
# ---------------------------------------------------------------------------


def test_short_audio_left_padded_to_8s():
    audio = np.ones(16000, dtype=np.float32)  # 1 second
    out = truncate_or_pad_to_last_n_seconds(audio)
    assert len(out) == 8 * 16000
    assert out[: 7 * 16000].sum() == 0  # zeros at the front
    assert out[-16000:].sum() == 16000  # audio at the end


def test_long_audio_truncated_to_last_8s():
    audio = np.arange(10 * 16000, dtype=np.float32)
    out = truncate_or_pad_to_last_n_seconds(audio)
    assert len(out) == 8 * 16000
    assert out[-1] == audio[-1]  # the END is kept


def test_exact_8s_untouched():
    audio = np.ones(8 * 16000, dtype=np.float32)
    assert truncate_or_pad_to_last_n_seconds(audio) is audio


# ---------------------------------------------------------------------------
# SmartTurn wiring: fake session + fake feature extractor, no ONNX load
# ---------------------------------------------------------------------------


class _FakeExtractor:
    def __call__(self, audio, **kwargs):
        class _T:
            input_features = np.zeros((1, 80, 3000), dtype=np.float32)

        return _T()


class _FakeSession:
    def __init__(self, probability: float) -> None:
        self.probability = probability
        self.ran = False

    def run(self, _names, _feeds):
        self.ran = True
        return [np.array([[self.probability]])]


def _smart_turn(probability: float) -> SmartTurn:
    s = object.__new__(SmartTurn)
    s._session = _FakeSession(probability)
    s._feature_extractor = _FakeExtractor()
    return s


@pytest.mark.parametrize(
    "prob,expected",
    [(0.9, True), (0.5, False), (0.1, False)],
)
def test_is_complete_threshold(prob: float, expected: bool):
    s = _smart_turn(prob)
    complete, returned = s.is_complete(np.zeros(16000, dtype=np.float32))
    assert complete is expected
    assert returned == prob


# ---------------------------------------------------------------------------
# Capture-loop integration: Smart Turn decides the end of turn
# ---------------------------------------------------------------------------


class _FakeVAD:
    def __init__(self) -> None:
        self.resets = 0

    def reset_states(self) -> None:
        self.resets += 1

    def __call__(self, frame: np.ndarray, sr: int) -> float:
        return 1.0 if float(np.sqrt(np.mean(frame**2))) > 0.05 else 0.0


class _FakeTranscriber:
    def process_chunk(self, pcm16_bytes: bytes) -> dict | None:
        return None

    def get_final(self) -> str | None:
        return "final words"


class _FakeSmartTurn:
    def __init__(self, complete: bool) -> None:
        self.complete = complete
        self.calls = 0
        self.durations_sec: list[float] = []

    def is_complete(self, audio: np.ndarray) -> tuple[bool, float]:
        self.calls += 1
        self.durations_sec.append(len(audio) / 16000)
        return self.complete, 0.9 if self.complete else 0.1


def _pipeline(smart_turn) -> AudioPipeline:
    p = AudioPipeline.__new__(AudioPipeline)
    p._silero_model = _FakeVAD()
    p.transcriber = _FakeTranscriber()
    p.speech_trigger_frames = SPEECH_TRIGGER_FRAMES
    p.speech_threshold = SILERO_THRESHOLD
    p._smart_turn = smart_turn
    return p


_SPEECH = (np.full(FRAME_SIZE, 0.3, dtype=np.float32) * 32767).astype(np.int16).tobytes()
_SILENCE = np.zeros(FRAME_SIZE, dtype=np.int16).tobytes()


@pytest.mark.asyncio
async def test_complete_verdict_ends_turn_at_quick_silence():
    smart = _FakeSmartTurn(complete=True)
    p = _pipeline(smart)
    queue: asyncio.Queue = asyncio.Queue()
    for _ in range(SPEECH_TRIGGER_FRAMES):
        await queue.put(_SPEECH)
    for _ in range(SILENCE_END_FRAMES_QUICK + 4):
        await queue.put(_SILENCE)

    audio = await asyncio.wait_for(p.stream_capture(queue), timeout=5)

    assert smart.calls == 1
    # turn closed after only the quick silence, not the legacy 12-frame tail
    assert len(audio) == (SPEECH_TRIGGER_FRAMES + SILENCE_END_FRAMES_QUICK) * FRAME_SIZE
    assert smart.durations_sec[0] == pytest.approx(len(audio) / 16000)


@pytest.mark.asyncio
async def test_incomplete_verdict_keeps_listening_until_force_cap():
    smart = _FakeSmartTurn(complete=False)
    p = _pipeline(smart)
    queue: asyncio.Queue = asyncio.Queue()
    for _ in range(SPEECH_TRIGGER_FRAMES):
        await queue.put(_SPEECH)
    # more silence than the force-cap could ever need
    for _ in range(SILENCE_END_FRAMES_QUICK + 6 * 8 + 20):
        await queue.put(_SILENCE)

    audio = await asyncio.wait_for(p.stream_capture(queue), timeout=5)

    # the model said "still talking" repeatedly; the cap is what finally ends it
    assert smart.calls == 6  # checks at 6,12,18,24,30,36 silence frames
    assert len(audio) == (SPEECH_TRIGGER_FRAMES + SILENCE_END_FRAMES_QUICK + 6 * 5) * FRAME_SIZE


@pytest.mark.asyncio
async def test_streaming_path_uses_smart_turn_too():
    smart = _FakeSmartTurn(complete=True)
    p = _pipeline(smart)
    queue: asyncio.Queue = asyncio.Queue()
    for _ in range(SPEECH_TRIGGER_FRAMES):
        await queue.put(_SPEECH)
    for _ in range(SILENCE_END_FRAMES_QUICK + 4):
        await queue.put(_SILENCE)

    text = await asyncio.wait_for(
        p.stream_capture_and_transcribe(queue), timeout=5
    )
    assert text == "final words"
    assert smart.calls == 1


def test_legacy_tail_when_smart_turn_missing():
    p = _pipeline(None)
    assert p._smart_turn is None
    # sanity: the legacy constants are what the fallback branch compares against
    assert SILENCE_END_FRAMES == 12
    assert SMART_TURN_RECHECK_STRIDE == 6


def test_get_smart_turn_returns_none_on_failure(monkeypatch):
    from yumii.audio import smart_turn as st

    def _boom(*a, **k):
        raise RuntimeError("no model")

    monkeypatch.setattr(st, "SmartTurn", _boom)
    assert get_smart_turn() is None
