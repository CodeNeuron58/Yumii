"""Tests for the fact extraction engine."""

from __future__ import annotations

import pytest

from yumii.agent.fact_extractor import (
    _format_messages_for_prompt,
    _parse_extraction_json,
    extract_facts,
)


class FakeAIMessage:
    """Fake LangChain message response for mocking."""

    def __init__(self, content: str) -> None:
        self.content = content


# ---------------------------------------------------------------------------
# _format_messages_for_prompt
# ---------------------------------------------------------------------------


def test_format_messages_basic() -> None:
    messages = [
        {"role": "user", "content": "I like jazz."},
        {"role": "assistant", "content": "That's cool!"},
    ]
    text = _format_messages_for_prompt(messages)
    assert "[User]: I like jazz." in text
    assert "[Assistant]: That's cool!" in text


def test_format_messages_missing_role_defaults_to_user() -> None:
    messages = [{"content": "Hello"}]
    text = _format_messages_for_prompt(messages)
    assert "[User]: Hello" in text


# ---------------------------------------------------------------------------
# _parse_extraction_json
# ---------------------------------------------------------------------------


def test_parse_plain_json() -> None:
    raw = '{"facts":[{"fact":"likes tea","category":"preference","confidence":0.9}]}'
    result = _parse_extraction_json(raw)
    assert len(result) == 1
    assert result[0]["fact"] == "likes tea"
    assert result[0]["category"] == "preference"


def test_parse_json_with_markdown_fences() -> None:
    raw = '```json\n{"facts":[{"fact":"has cat","category":"identity","confidence":0.8}]}\n```'
    result = _parse_extraction_json(raw)
    assert len(result) == 1
    assert result[0]["fact"] == "has cat"


def test_parse_json_with_extra_prose() -> None:
    raw = 'Sure! Here is the JSON:\n{"facts":[{"fact":"enjoys hiking","category":"habit","confidence":0.95}]}'
    result = _parse_extraction_json(raw)
    assert len(result) == 1
    assert result[0]["category"] == "habit"


def test_parse_empty_facts() -> None:
    raw = '{"facts":[]}'
    result = _parse_extraction_json(raw)
    assert result == []


def test_parse_invalid_json_returns_empty() -> None:
    raw = "this is not json"
    result = _parse_extraction_json(raw)
    assert result == []


# ---------------------------------------------------------------------------
# extract_facts (with mocked LLM)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_facts_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """extract_facts should parse the LLM response and return validated facts."""

    async def fake_ainvoke(_self, _messages: list) -> FakeAIMessage:
        return FakeAIMessage(
            '{"facts":[\n'
            '  {"fact":"User likes jazz","category":"preference","confidence":0.95},\n'
            '  {"fact":"User lives in Tokyo","category":"identity","confidence":0.8}\n'
            ']}'
        )

    # Patch the LLM instance's ainvoke method
    monkeypatch.setattr(
        "yumii.agent.fact_extractor._get_extractor_llm",
        lambda: type("FakeLLM", (), {"ainvoke": fake_ainvoke})(),
    )

    facts = await extract_facts(
        [
            {"role": "user", "content": "I like jazz and I live in Tokyo."},
            {"role": "assistant", "content": "Nice!"},
        ]
    )
    assert len(facts) == 2
    assert facts[0]["fact"] == "User likes jazz"
    assert facts[0]["category"] == "preference"
    assert facts[1]["fact"] == "User lives in Tokyo"


@pytest.mark.asyncio
async def test_extract_facts_llm_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the LLM call fails, extract_facts should return an empty list."""

    async def fake_ainvoke(_self, _messages: list) -> None:
        raise RuntimeError("API rate limit")

    monkeypatch.setattr(
        "yumii.agent.fact_extractor._get_extractor_llm",
        lambda: type("FakeLLM", (), {"ainvoke": fake_ainvoke})(),
    )

    facts = await extract_facts([{"role": "user", "content": "Hello"}])
    assert facts == []


@pytest.mark.asyncio
async def test_extract_facts_empty_input() -> None:
    """Empty message list should short-circuit to an empty list."""
    facts = await extract_facts([])
    assert facts == []


@pytest.mark.asyncio
async def test_extract_facts_invalid_category_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown categories should fall back to 'general'."""

    async def fake_ainvoke(_self, _messages: list) -> FakeAIMessage:
        return FakeAIMessage(
            '{"facts":[{"fact":"test","category":"unknown_stuff","confidence":0.5}]}'
        )

    monkeypatch.setattr(
        "yumii.agent.fact_extractor._get_extractor_llm",
        lambda: type("FakeLLM", (), {"ainvoke": fake_ainvoke})(),
    )

    facts = await extract_facts([{"role": "user", "content": "test"}])
    assert len(facts) == 1
    assert facts[0]["category"] == "general"


@pytest.mark.asyncio
async def test_extract_facts_clamps_confidence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Confidence values outside 0–1 should be clamped."""

    async def fake_ainvoke(_self, _messages: list) -> FakeAIMessage:
        return FakeAIMessage(
            '{"facts":['
            '{"fact":"high","category":"general","confidence":9.9},'
            '{"fact":"low","category":"general","confidence":-0.5}'
            ']}'
        )

    monkeypatch.setattr(
        "yumii.agent.fact_extractor._get_extractor_llm",
        lambda: type("FakeLLM", (), {"ainvoke": fake_ainvoke})(),
    )

    facts = await extract_facts([{"role": "user", "content": "x"}])
    assert facts[0]["confidence"] == 1.0
    assert facts[1]["confidence"] == 0.0
