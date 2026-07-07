"""Tests for the personality manager and personality .txt files."""

from pathlib import Path

import pytest

from yumii.agent.personality_manager import (
    PERSONALITY_DESCRIPTIONS,
    PersonalityManager,
    personality_manager,
)


def test_all_six_personalities_have_files():
    """Every advertised personality must have a corresponding prompt file."""
    prompts_dir = Path(__file__).parent.parent / "src" / "yumii" / "assets" / "prompts"
    for name in PERSONALITY_DESCRIPTIONS:
        path = prompts_dir / f"{name}.txt"
        assert path.exists(), f"Missing prompt file: {path}"
        assert path.stat().st_size > 100, f"Prompt file is suspiciously small: {path}"


def test_personalities_have_descriptions():
    """Each personality must have a non-empty human-readable description."""
    assert len(PERSONALITY_DESCRIPTIONS) == 6
    for name, desc in PERSONALITY_DESCRIPTIONS.items():
        assert isinstance(name, str)
        assert isinstance(desc, str)
        assert len(desc) > 0


def test_manager_loads_known_personality():
    """Loading a known personality should return a non-empty prompt."""
    prompt = personality_manager.load_personality("caring")
    assert isinstance(prompt, str)
    assert len(prompt) > 100


def test_assembled_prompt_carries_the_synthesizer_contract():
    """The engine derives emotion/motion from plain text, so the prompt
    the model actually receives must state the plain-text rule. Since
    the core rewrite, that contract lives once in ``_core.txt`` instead
    of being repeated in every personality file — assert it at the
    assembly level, where it matters."""
    from yumii.agent.llm import _build_system_prompt

    prompt = _build_system_prompt("caring", None)
    assert "expression" in prompt.lower()
    assert "motion" in prompt.lower()
    assert "plain conversational text" in prompt.lower()


def test_manager_caches_loaded_prompts():
    """A second load should hit the cache (return the same object)."""
    mgr = PersonalityManager()
    first = mgr.load_personality("caring")
    second = mgr.load_personality("caring")
    # Cached strings are interned by Python; this is a strong identity check.
    assert first is second


def test_manager_raises_for_missing_personality():
    """A non-existent personality file must raise FileNotFoundError."""
    mgr = PersonalityManager()
    with pytest.raises(FileNotFoundError):
        mgr.load_personality("this_personality_does_not_exist")


def test_get_current_personality_returns_valid_value():
    """The current personality (from config) must be a known personality name."""
    name = personality_manager.get_current_personality()
    assert name in PERSONALITY_DESCRIPTIONS


def test_prompts_do_not_instruct_llm_to_emit_json():
    """PR 2 removed the structured YumiiResponse output path. The LLM
    now emits plain text and the synthesizer derives emotion/motion.
    No personality prompt may tell the LLM to wrap its reply in JSON
    or use ``response_text`` / structured-output syntax — that would
    leak JSON into the TTS pipeline (and the user would hear it
    spoken aloud).

    This test guards against accidental reintroduction of the
    pre-PR-2 ``response_format=YumiiResponse`` contract.
    """
    prompts_dir = Path(__file__).parent.parent / "src" / "yumii" / "assets" / "prompts"
    forbidden_phrases = (
        "Return ONLY structured JSON",
        "structured JSON with `response_text`",
        "respond with JSON",
        "return JSON",
        "<function>",  # legacy Groq workaround
    )
    for name in PERSONALITY_DESCRIPTIONS:
        prompt = (prompts_dir / f"{name}.txt").read_text(encoding="utf-8")
        for phrase in forbidden_phrases:
            assert phrase not in prompt, (
                f"Personality {name!r} still contains forbidden instruction "
                f"{phrase!r}. PR 2 changed the agent loop to plain text; "
                f"prompts must not instruct the LLM to emit JSON."
            )
