"""Tests for the token→sentence segmenter that feeds streaming TTS."""

import pytest

from yumii.tts.sentence_stream import SentenceSegmenter


def feed_all(segmenter: SentenceSegmenter, text: str, chunk: int = 3) -> list[str]:
    """Simulate a token stream: feed ``text`` in small chunks, then flush."""
    out: list[str] = []
    for i in range(0, len(text), chunk):
        out.extend(segmenter.feed(text[i : i + chunk]))
    tail = segmenter.flush()
    if tail:
        out.append(tail)
    return out


def test_single_sentence_flushes_on_boundary():
    seg = SentenceSegmenter()
    assert seg.feed("Hello there! ") == ["Hello there!"]
    assert seg.flush() is None


def test_sentences_arrive_incrementally_not_at_end():
    seg = SentenceSegmenter()
    first: list[str] = []
    # A sentence closes at punctuation followed by whitespace — the same
    # lookahead that keeps "3.14" in one piece. The space normally arrives
    # with the very next token, so the sentence is out before the next
    # sentence has generated.
    first.extend(seg.feed("Sure thing. "))
    assert first == ["Sure thing."]
    first.extend(seg.feed("And more. "))
    assert first == ["Sure thing.", "And more."]
    assert seg.flush() is None


def test_no_boundary_until_flush():
    seg = SentenceSegmenter()
    assert seg.feed("one two three") == []
    assert seg.feed(" four five") == []
    assert seg.flush() == "one two three four five"


def test_think_block_never_spoken():
    out = feed_all(SentenceSegmenter(), "<think>secret reasoning</think>Hello!")
    assert out == ["Hello!"]


def test_think_block_split_across_tokens():
    seg = SentenceSegmenter()
    out: list[str] = []
    for piece in ("<thi", "nk>hi", "dden</thi", "nk>Hi there. "):
        out.extend(seg.feed(piece))
    assert out == ["Hi there."]
    assert seg.flush() is None


def test_unterminated_think_block_speaks_nothing():
    seg = SentenceSegmenter()
    out: list[str] = []
    out.extend(seg.feed("Fine. <think>internal"))
    assert out == ["Fine."]
    assert seg.flush() is None  # everything inside the unterminated block is dropped


def test_thinking_variant_tag():
    out = feed_all(SentenceSegmenter(), "<thinking>hmm</thinking>Ok.")
    assert out == ["Ok."]


def test_decimal_not_split():
    out = feed_all(SentenceSegmenter(), "It costs 3.14 dollars exactly.")
    assert out == ["It costs 3.14 dollars exactly."]


def test_long_punctuation_free_buffer_flushes_at_clause():
    text = "a " * 150 + "and then the rest of the story keeps going"
    out = feed_all(SentenceSegmenter(), text)
    assert len(out) >= 2  # clause-boundary flush kept the tail from stalling
    assert " ".join(out).split() == text.split()


def test_multiple_boundaries_in_one_token():
    seg = SentenceSegmenter()
    out = seg.feed("One. Two. Three. ")
    assert out == ["One.", "Two.", "Three."]


def test_whitespace_only_tokens_are_ignored():
    seg = SentenceSegmenter()
    assert seg.feed("   ") == []
    assert seg.feed("Hi. ") == ["Hi."]


def test_empty_stream_flushes_none():
    assert SentenceSegmenter().flush() is None


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Hi!", ["Hi!"]),
        ("A. B.", ["A.", "B."]),
        ("No punctuation here at all", ["No punctuation here at all"]),
    ],
)
def test_shapes(text: str, expected: list[str]):
    assert feed_all(SentenceSegmenter(), text, chunk=2) == expected
