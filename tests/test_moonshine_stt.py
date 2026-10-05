"""MoonshineStreamingSTT: rolling-window partials over the offline v2 decoder.

Tested against a fake offline recognizer (no sherpa import, no downloads).
The provider inherits the rolling-window pattern from _RollingWindowSTT —
partials every ~2s of new audio (diff-suppressed), full-utterance decode at
end-of-turn.
"""

import numpy as np

from yumii.audio.stt_providers import MoonshineStreamingSTT

_FRAME_BYTES = (np.full(512, 1000, dtype=np.int16)).tobytes()  # 512 samples = 32ms


class _FakeOfflineStream:
    def __init__(self, recognizer):
        self._recognizer = recognizer
        self.samples = 0

    def accept_waveform(self, sample_rate, waveform):
        self.samples += len(waveform)

    @property
    def result(self):
        text = self._recognizer.texts[
            min(self._recognizer.calls - 1, len(self._recognizer.texts) - 1)
        ]
        return type("R", (), {"text": text})


class _FakeOfflineRecognizer:
    """Offline decode returns canned text per call."""

    def __init__(self, texts: list[str]):
        self.texts = list(texts)
        self.calls = 0
        self.inputs: list[np.ndarray] = []

    def create_stream(self):
        return _FakeOfflineStream(self)

    def decode_stream(self, stream):
        self.calls += 1
        self.inputs.append(stream.samples)


def _moonshine(texts: list[str]) -> tuple[MoonshineStreamingSTT, _FakeOfflineRecognizer]:
    fake = _FakeOfflineRecognizer(texts)
    s = MoonshineStreamingSTT.__new__(MoonshineStreamingSTT)  # no sherpa import
    s._recognizer = fake
    s._utterance = []
    s._tail = np.empty(0, dtype=np.int16)
    s._frames_since_partial = 0
    s._last_partial = ""
    return s, fake


def _feed_frames(stt: MoonshineStreamingSTT, seconds: float) -> list[dict | None]:
    import math

    out = []
    for _ in range(math.ceil(seconds * 16000 / 512)):
        result = stt.process_chunk(_FRAME_BYTES)
        if result:
            out.append(result)
    return out


def test_partial_after_two_seconds_and_diff_suppression():
    s, _ = _moonshine(["hello", "hello world", "hello world"])

    first = _feed_frames(s, 2.0)
    assert [p["text"] for p in first] == ["hello"]

    second = _feed_frames(s, 2.0)
    assert [p["text"] for p in second] == ["hello world"]

    third = _feed_frames(s, 2.0)
    assert third == []  # unchanged — suppressed


def test_get_final_decodes_full_utterance():
    s, fake = _moonshine(["partial text", "the final words"])
    _feed_frames(s, 2.0)

    final = s.get_final()

    assert final == "the final words"
    assert len(fake.inputs) == 2  # partial decode + final decode
    assert fake.inputs[-1] == 63 * 512  # the FULL fed utterance, not the window
    assert s._utterance == [] and s._last_partial == ""


def test_moonshine_window_is_six_seconds():
    s, _ = _moonshine(["hello"])
    _feed_frames(s, 10.0)
    assert len(s._tail) == int(s._PARTIAL_WINDOW_SEC * s._RATE)


def test_transcribe_fallback_uses_one_offline_decode():
    s, fake = _moonshine(["one shot"])

    text = s.transcribe(np.full(32000, 1000, dtype=np.int16))

    assert text == "one shot"
    assert fake.calls == 1
