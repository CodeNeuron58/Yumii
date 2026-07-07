"""Tests for cache-friendly system prompt assembly.

Provider prefix (KV) caching only works when requests share a
byte-identical prefix, so these tests pin the properties the layout
depends on: static content first, date after it, facts last, and
perfect stability between calls with the same inputs.
"""

from __future__ import annotations

import datetime

from yumii.agent.llm import _build_system_prompt
from yumii.agent.personality_manager import personality_manager


def test_identical_inputs_produce_identical_prompts():
    """Two builds in the same session must be byte-identical (cache hit)."""
    a = _build_system_prompt("caring", "  - likes jazz")
    b = _build_system_prompt("caring", "  - likes jazz")
    assert a == b


def test_layout_order_static_then_date_then_facts():
    prompt = _build_system_prompt("tsundere", "  - has a cat named Mochi")
    core_start = prompt.index("YOU ARE YUMII")
    persona_pos = prompt.index("PERSONALITY: TSUNDERE")
    date_pos = prompt.index("Today is ")
    facts_pos = prompt.index("What you know about the user:")
    assert core_start < persona_pos < date_pos < facts_pos


def test_static_prefix_unchanged_by_fact_updates():
    """New facts must only mutate the TAIL — the static prefix (core +
    personality + date) has to stay byte-identical or history caching
    dies every time a fact is extracted."""
    without = _build_system_prompt("genki", None)
    with_facts = _build_system_prompt("genki", "  - is learning Rust")
    assert with_facts.startswith(without)


def test_date_has_no_clock_time():
    """A minute-resolution timestamp in the prompt was the original
    cache-killer; only the date may appear."""
    prompt = _build_system_prompt("kuudere", None)
    today = datetime.datetime.now()
    assert today.strftime("%B") in prompt  # date present
    assert today.strftime("%I:%M") not in prompt  # clock time absent
    assert "current time is" not in prompt.lower()


def test_all_personalities_share_the_core():
    for p in ("caring", "tsundere", "genki", "kuudere", "yandere", "dandere"):
        prompt = _build_system_prompt(p, None)
        assert "YOU ARE YUMII" in prompt, p
        assert "CRITICAL RULE" in prompt, p
        assert f"PERSONALITY: {p.upper()}" in prompt, p


def test_core_prompt_loads_and_is_substantial():
    core = personality_manager.load_core_prompt()
    assert len(core) > 2000  # a real companion prompt, not a stub
    # spoken-voice contract must be stated
    assert "SPOKEN ALOUD" in core
