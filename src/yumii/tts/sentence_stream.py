"""Turn a raw LLM token stream into speakable sentences, thinking-blocks stripped.

Feeds the engine's token→TTS streaming path: a sentence is emitted the moment
its punctuation closes, so synthesis starts while the model is still
generating. ``<think>…</think>`` blocks never reach speech — including one
left unterminated at stream end. Synchronous and deterministic, called per
token; the same text always yields the same segmentation.
"""

from __future__ import annotations

import re

_THINK_OPEN = re.compile(r"<think(?:ing)?>", re.IGNORECASE)
_THINK_CLOSE = re.compile(r"</think(?:ing)?>", re.IGNORECASE)

_SHAPES_OPEN = ("<think>", "<thinking>")
_SHAPES_CLOSE = ("</think>", "</thinking>")

# A marker cut short by the token boundary could still complete with the next
# token, so that tail must be held back instead of spoken.
_MAX_PARTIAL = len("</thinking>") - 1

# Sentence boundaries: ASCII terminators need trailing whitespace; CJK
# terminators (。！？) split immediately (no spaces in CJK text).
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…])\s+|(?<=[。！？])")
_CLAUSE_BOUNDARY = re.compile(r"(?<=[,;:])\s+")

# "Mr." / "e.g." — a boundary after these is not a sentence end. The splitter
# skips it and looks for the next one.
_ABBREV_TAIL = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|St|Sr|Jr|Prof|vs|etc|Inc|Ltd|No|approx|e\.g|i\.e)\.$",
    re.IGNORECASE,
)


def merge_abbreviation_fragments(parts: list[str]) -> list[str]:
    """Join split fragments whose predecessor ended in an abbreviation.

    Shared with the TTS chunker, which splits with the same regex.
    """
    merged: list[str] = []
    for part in parts:
        if merged and _ABBREV_TAIL.search(merged[-1].rstrip()):
            merged[-1] = f"{merged[-1].rstrip()} {part.strip()}"
        else:
            merged.append(part)
    return merged

# A punctuation-free ramble longer than this flushes at the last clause
# boundary so speech starts before the model stops for breath.
_MAX_PENDING_CHARS = 240


def _partial_marker_len(text: str, shapes: tuple[str, ...]) -> int:
    """Length of ``text``'s suffix that could still grow into a full marker."""
    for cut in range(min(_MAX_PARTIAL, len(text)), 0, -1):
        tail = text[-cut:].lower()
        if any(shape.startswith(tail) and tail != shape for shape in shapes):
            return cut
    return 0


def _split_sentences(text: str, final: bool) -> tuple[list[str], str]:
    """Split complete sentences off the front of ``text``; return (spoken, rest)."""
    if not text.strip():
        return [], text

    emitted: list[str] = []
    rest = text
    start = 0
    while True:
        # Emit at the FIRST closed boundary that isn't an abbreviation
        # ("Mr." / "e.g." — the following boundary is the real one).
        m = _SENTENCE_BOUNDARY.search(rest, start)
        if m is None:
            break
        candidate = rest[: m.end()].strip()
        if _ABBREV_TAIL.search(candidate):
            start = m.end()
            continue
        if candidate:
            emitted.append(candidate)
        rest = rest[m.end():]
        start = 0

    if final:
        if rest.strip():
            emitted.append(rest.strip())
        return emitted, ""

    if len(rest) > _MAX_PENDING_CHARS:
        last_clause = None
        for m in _CLAUSE_BOUNDARY.finditer(rest):
            last_clause = m
        if last_clause is not None:
            sentence = rest[: last_clause.end()].strip()
            rest = rest[last_clause.end():]
            if sentence:
                emitted.append(sentence)
        else:
            # No natural boundary at all — flush whole to bound first-word latency.
            emitted.append(rest.strip())
            rest = ""
    return emitted, rest


class SentenceSegmenter:
    """Accumulate tokens; emit speakable sentence chunks as boundaries close."""

    def __init__(self) -> None:
        """Start empty, outside any think block."""
        self._raw = ""
        self._inside_think = False

    def feed(self, token: str) -> list[str]:
        """Consume one token; return 0..n sentences that became speakable."""
        if not token:
            return []
        self._raw += token
        return self._resolve(final=False)

    def flush(self) -> str | None:
        """End of stream: emit any remainder; ``None`` if nothing (or all think) is left."""
        out = self._resolve(final=True)
        text = " ".join(s for s in out if s).strip()
        return text or None

    def _resolve(self, final: bool) -> list[str]:
        out: list[str] = []
        while True:
            if self._inside_think:
                m = _THINK_CLOSE.search(self._raw)
                if m:
                    self._raw = self._raw[m.end():]
                    self._inside_think = False
                    continue
                if final:
                    self._raw = ""
                    return out
                hold = _partial_marker_len(self._raw, _SHAPES_CLOSE)
                self._raw = self._raw[len(self._raw) - hold:] if hold else ""
                return out

            m = _THINK_OPEN.search(self._raw)
            if m:
                spoken, _ = _split_sentences(self._raw[: m.start()], final=True)
                out.extend(spoken)
                self._raw = self._raw[m.end():]
                self._inside_think = True
                continue

            if final:
                spoken, _ = _split_sentences(self._raw, final=True)
                self._raw = ""
                out.extend(spoken)
                return out

            hold = _partial_marker_len(self._raw, _SHAPES_OPEN)
            safe = self._raw[: len(self._raw) - hold] if hold else self._raw
            spoken, remainder = _split_sentences(safe, final=False)
            if not spoken and remainder == safe:
                return out
            out.extend(spoken)
            self._raw = remainder + self._raw[len(safe):]
            if not spoken:
                return out


__all__ = ["SentenceSegmenter", "merge_abbreviation_fragments"]
