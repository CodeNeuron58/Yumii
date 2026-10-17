"""LocalSTT streaming partials: rolling-window re-decode without true streaming.

Whisper can't stream — so while the user speaks, LocalSTT re-decodes the last
few seconds every ~2s (diff-suppressed partials), and decodes the FULL
utterance at end-of-turn. All with a fake Whisper model: no downloads, no
network.
"""

from concurrent.futures import Future
from types import SimpleNamespace

import numpy as np

from yumii.audio.stt_providers import LocalSTT, _RollingWindowSTT

_FRAME_BYTES = (np.full(512, 1000, dtype=np.int16)).tobytes()  # 512 samples = 32ms


class _FakeWhisper:
    """Returns canned text per transcribe call; records the audio it saw."""

    def __init__(self, texts: list[str]):
        self.texts = list(texts)
        self.calls = 0
        self.inputs: list[np.ndarray] = []

    def transcribe(self, audio, **kw):
        self.calls += 1
        self.inputs.append(audio)
        text = self.texts[min(self.calls - 1, len(self.texts) - 1)]
        return [SimpleNamespace(text=text, no_speech_prob=0.0)], None


class _InlineExecutor:
    """Runs the partial decode at submit time — deterministic tests."""

    def submit(self, fn, *args):
        f: Future = Future()
        f.set_result(fn(*args))
        return f


class _ManualExecutor:
    """Holds partial decodes until run_all() — models a slow background thread."""

    def __init__(self) -> None:
        self.pending: list = []

    def submit(self, fn, *args):
        f: Future = Future()
        self.pending.append((f, fn, args))
        return f

    def run_all(self) -> None:
        for f, fn, args in self.pending:
            f.set_result(fn(*args))
        self.pending.clear()


def _local_stt(texts: list[str], executor=None) -> tuple[LocalSTT, _FakeWhisper]:
    s = LocalSTT.__new__(LocalSTT)  # no model load
    _RollingWindowSTT.__init__(s)
    s._executor = executor or _InlineExecutor()
    s._whisper = _FakeWhisper(texts)
    return s, s._whisper


def _decode_cost_clock(costs: list[float]):
    """A clock under which successive decodes appear to take ``costs`` seconds."""
    state = {"t": 0.0, "start": True, "i": 0, "cost": 0.0}

    def clock() -> float:
        if state["start"]:  # decode start
            state["t"] += 100.0
            state["cost"] = costs[min(state["i"], len(costs) - 1)]
            state["i"] += 1
            state["start"] = False
            return state["t"]
        state["start"] = True
        return state["t"] + state["cost"]

    return clock


def _feed_frames(stt: LocalSTT, seconds: float) -> list[dict | None]:
    """Feed ``seconds`` of audio one frame at a time; return partials emitted."""
    import math

    out = []
    for _ in range(math.ceil(seconds * 16000 / 512)):
        result = stt.process_chunk(_FRAME_BYTES)
        if result:
            out.append(result)
    return out


# ── Partials ───────────────────────────────────────────────────────────


def test_partial_emitted_after_two_seconds_of_new_audio():
    s, fake = _local_stt(["hello there", "hello there friend"])

    assert _feed_frames(s, 1.5) == []  # below the 2s gate — no decode yet
    first = _feed_frames(s, 1.0)
    assert [p["text"] for p in first] == ["hello there"]
    assert fake.calls == 1

    second = _feed_frames(s, 2.0)
    assert [p["text"] for p in second] == ["hello there friend"]


def test_unchanged_text_is_suppressed():
    s, fake = _local_stt(["hello", "hello"])
    _feed_frames(s, 2.0)
    assert _feed_frames(s, 2.0) == []  # same text — the orb already shows it
    assert fake.calls == 2             # it still decoded; just didn't re-emit


def test_rolling_window_is_capped():
    s, _ = _local_stt(["a", "b", "c", "d", "e", "f"])
    _feed_frames(s, 10.0)
    assert len(s._tail) == int(s._PARTIAL_WINDOW_SEC * s._RATE)


# ── Final decode ───────────────────────────────────────────────────────


def test_get_final_decodes_the_full_utterance_and_resets():
    s, fake = _local_stt(["hello", "the full sentence"])
    _feed_frames(s, 2.0)

    final = s.get_final()

    assert final == "the full sentence"
    assert fake.calls == 2                 # partial decode + final decode
    # the final decode covered the ENTIRE fed utterance (63 frames), not just
    # the 4s rolling window
    assert len(fake.inputs[-1]) == 63 * 512
    assert s._utterance == [] and s._last_partial == ""  # state reset


def test_get_final_is_none_below_the_duration_floor():
    s, fake = _local_stt(["hello"])
    _feed_frames(s, 0.2)  # 0.2s < the 0.7s floor

    assert s.get_final() is None
    assert fake.calls == 0  # never even asked Whisper


def test_state_resets_between_utterances():
    """After get_final, the partial gate restarts from zero for the next
    utterance — no leftover counter should fire a partial on frame one."""
    s, _ = _local_stt(["hello"])  # constant text — only the gating is under test
    _feed_frames(s, 2.0)
    assert s.get_final() == "hello"

    # first frame of the NEXT utterance: a stale counter would emit instantly
    assert s.process_chunk(_FRAME_BYTES) is None

    frames = _feed_frames(s, 2.0)
    assert [f["text"] for f in frames] == ["hello"]  # fires at its own 2s gate
    assert s.get_final() == "hello"


# ── Partials are opportunistic: never block, never stale, off when slow ─


def test_partials_never_block_capture():
    """While a partial decodes in the background, frames keep flowing and no
    second decode is queued behind it."""
    manual = _ManualExecutor()
    s, fake = _local_stt(["hello there"], executor=manual)

    assert _feed_frames(s, 5.0) == []   # one decode submitted, still running
    assert len(manual.pending) == 1     # ...and nothing queued behind it
    assert fake.calls == 0

    manual.run_all()
    assert s.process_chunk(_FRAME_BYTES) == {"type": "partial_transcript", "text": "hello there"}


def test_a_partial_finishing_after_the_turn_ended_is_dropped():
    manual = _ManualExecutor()
    s, _ = _local_stt(["stale words"], executor=manual)
    _feed_frames(s, 2.0)
    assert len(manual.pending) == 1

    s.reset()          # the turn was abandoned while the partial decoded
    manual.run_all()

    assert s.process_chunk(_FRAME_BYTES) is None  # stale — never shown


def test_slow_partials_switch_themselves_off():
    """Whisper base on a laptop CPU: ~2.2s per 4s partial vs a 1s budget."""
    s, fake = _local_stt(["a", "b", "c", "d"])
    s._clock = _decode_cost_clock([2.2])

    _feed_frames(s, 4.1)               # two over-budget partials in a row
    assert s._partials_enabled is False
    calls = fake.calls

    _feed_frames(s, 6.0)
    assert fake.calls == calls         # no more partial decodes...
    assert s.get_final() is not None
    assert fake.calls == calls + 1     # ...but the final still decodes


def test_one_slow_partial_does_not_switch_them_off():
    s, _ = _local_stt(["a", "b", "c"])
    s._clock = _decode_cost_clock([2.2, 0.1, 2.2])

    _feed_frames(s, 6.0)  # slow, fast, slow — never two slow in a row

    assert s._partials_enabled is True


def test_calibration_switches_partials_off_on_a_slow_machine():
    """One silent decode at load predicts the partial cost (Whisper pads to 30s)."""
    s, fake = _local_stt(["", "hello"])
    s._clock = _decode_cost_clock([2.07])

    s._calibrate_partials()

    assert s._partials_enabled is False
    assert _feed_frames(s, 4.0) == [] and fake.calls == 1  # only the calibration


def test_calibration_keeps_partials_on_a_fast_machine():
    s, _ = _local_stt(["", "hello"])
    s._clock = _decode_cost_clock([0.3])

    s._calibrate_partials()

    assert s._partials_enabled is True


def test_reset_discards_without_decoding():
    s, fake = _local_stt(["hello"])
    _feed_frames(s, 1.0)

    s.reset()

    assert fake.calls == 0
    assert s.get_final() is None  # nothing left to decode


def test_final_decode_is_peak_normalized():
    """Parity with the 0.14 batch path: quiet speech is scaled to a 0.9 peak."""
    s, fake = _local_stt(["hello"])
    _feed_frames(s, 1.0)  # 1000/32768 ≈ 0.03 peak — a quiet mic

    s.get_final()

    assert abs(float(np.max(np.abs(fake.inputs[-1]))) - 0.9) < 1e-4
