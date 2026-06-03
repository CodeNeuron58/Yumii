"""Tests for the personality manager and personality .txt files."""

from pathlib import Path

import pytest

from yumi.agent.personality_manager import (
    PERSONALITY_DESCRIPTIONS,
    PersonalityManager,
    personality_manager,
)


def test_all_six_personalities_have_files():
    """Every advertised personality must have a corresponding prompt file."""
    prompts_dir = Path(__file__).parent.parent / "src" / "yumi" / "assets" / "prompts"
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
    # The prompt must instruct the LLM to use a structured response,
    # because the engine depends on it for emotion/motion data.
    assert "expression" in prompt.lower()
    assert "motion" in prompt.lower()


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
