"""NemotronStreamingSTT: true-streaming provider over sherpa-onnx.

All tested against a stateful fake recognizer — no sherpa-onnx import, no
model download. The fake mirrors the real streaming contract: pending audio
buffers until a full 560ms chunk exists, decode consumes one chunk, and
input_finished flushes the tail and reveals everything. Verifies the shape
the pipeline consumes: diff-suppressed partials from process_chunk, and a
get_final that flushes (input_finished) and resets for the next utterance.
"""

import numpy as np

from yumii.audio.stt_providers import NemotronStreamingSTT

_FRAME_BYTES = (np.full(512, 1000, dtype=np.int16)).tobytes()  # 512 samples = 32ms


class _FakeStream:
    """Decode state is PER STREAM (real sherpa: each stream owns its cache)."""

    def __init__(self, recognizer):
        self._recognizer = recognizer
        self.pending = 0  # samples accepted but not yet decoded
        self.finished = False
        self.revealed = 0

    def accept_waveform(self, sample_rate, waveform):
        self.pending += len(waveform)

    def input_finished(self):
        self.finished = True
        # the tail flush reveals the full utterance
        self.revealed = self._recognizer.max_revealed

    def __hash__(self):
        return id(self)


class _FakeRecognizer:
    """Text reveals one extra word per decoded 560ms chunk."""

    _CHUNK = 17920  # samples (560ms @ 16k)

    def __init__(self, words: list[str]):
        self.words = words
        self.max_revealed = len(words)
        self.streams = 0

    def create_stream(self):
        self.streams += 1
        return _FakeStream(self)

    def is_ready(self, stream):
        return stream.pending >= self._CHUNK or (stream.finished and stream.pending > 0)

    def decode_stream(self, stream):
        if stream.pending >= self._CHUNK:
            stream.pending -= self._CHUNK
            stream.revealed = min(stream.revealed + 1, self.max_revealed)
        elif stream.finished and stream.pending > 0:
            # the tail flush consumes the remainder and reveals everything
            stream.pending = 0
            stream.revealed = self.max_revealed

    def get_result(self, stream):
        return " ".join(self.words[: stream.revealed])


def _provider(words: list[str]) -> tuple[NemotronStreamingSTT, _FakeRecognizer]:
    fake = _FakeRecognizer(words)
    s = NemotronStreamingSTT.__new__(NemotronStreamingSTT)  # no sherpa import
    s._recognizer = fake
    s._stream = None
    s._last_partial = ""
    return s, fake


def _feed_frames(stt: NemotronStreamingSTT, frames: int) -> list[dict | None]:
    """Feed ``frames`` one at a time; return partials emitted."""
    out = []
    for _ in range(frames):
        result = stt.process_chunk(_FRAME_BYTES)
        if result:
            out.append(result)
    return out


# ── Partials ───────────────────────────────────────────────────────────


def test_no_partial_before_one_full_chunk():
    """512 samples < the model's 560ms internal chunk — nothing to say yet."""
    s, _ = _provider(["alpha", "beta", "gamma", "delta"])
    assert _feed_frames(s, 1) == []


def test_partial_emitted_per_revealed_chunk():
    s, _ = _provider(["alpha", "beta", "gamma", "delta"])
    got = [r["text"] for r in _feed_frames(s, 80)]  # 40960 samples → 2 chunks decode

    assert got == ["alpha", "alpha beta"]


def test_partial_emits_only_on_change():
    """The fake keeps revealing 'alpha' — repeats must be suppressed."""
    s, _ = _provider(["alpha", "alpha", "alpha", "alpha"])
    s._recognizer.max_revealed = 1

    got = [r["text"] for r in _feed_frames(s, 200)]  # 6+ chunks, all "alpha"

    assert got == ["alpha"]


# ── Final flush ────────────────────────────────────────────────────────


def test_get_final_flushes_and_resets():
    s, fake = _provider(["alpha", "beta"])
    s._recognizer.max_revealed = 2

    got = _feed_frames(s, 40)  # one chunk decoded → "alpha" partial
    final = s.get_final()

    assert got == [{"type": "partial_transcript", "text": "alpha"}]
    assert final == "alpha beta"   # input_finished revealed the rest
    assert s._stream is None       # fresh stream for the next utterance
    assert s._last_partial == ""   # partial state reset


def test_get_final_with_no_stream_is_none():
    s, _ = _provider(["alpha"])
    assert s.get_final() is None
    assert s._recognizer.streams == 0  # never created a stream


def test_transcribe_fallback_is_one_shot():
    s, fake = _provider(["alpha beta"])
    s._recognizer.max_revealed = 2

    text = s.transcribe(np.full(32000, 1000, dtype=np.int16))

    assert text == "alpha beta"
    assert fake.streams == 1          # its own throwaway stream
    assert s._stream is None          # the streaming state is untouched


def test_new_utterance_reveals_from_zero():
    """After get_final, a fresh stream reveals nothing until new audio feeds
    it — no leftover words from the previous utterance."""
    s, _ = _provider(["alpha", "beta"])
    s._recognizer.max_revealed = 2
    for _ in range(40):
        s.process_chunk(_FRAME_BYTES)
    s.get_final()

    r = s.process_chunk(_FRAME_BYTES)  # first frame of the NEXT utterance
    assert r is None
