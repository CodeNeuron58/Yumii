"""LocalSTT streaming partials: rolling-window re-decode without true streaming.

Whisper can't stream — so while the user speaks, LocalSTT re-decodes the last
few seconds every ~2s (diff-suppressed partials), and decodes the FULL
utterance at end-of-turn. All with a fake Whisper model: no downloads, no
network.
"""

from types import SimpleNamespace

import numpy as np

from yumii.audio.stt_providers import LocalSTT

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


def _local_stt(texts: list[str]) -> tuple[LocalSTT, _FakeWhisper]:
    s = LocalSTT.__new__(LocalSTT)  # no model load
    s._whisper = _FakeWhisper(texts)
    s._utterance = []
    s._tail = np.empty(0, dtype=np.int16)
    s._frames_since_partial = 0
    s._last_partial = ""
    return s, s._whisper


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
