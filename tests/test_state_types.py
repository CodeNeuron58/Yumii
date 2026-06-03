"""Tests for the core state types.

These tests pin the shape of `MainState` so that any future change to
the conversation state is intentional and visible in code review.
"""

from yumii.core.types import PERSONALITY_TYPE, MainState


def test_main_state_has_required_fields() -> None:
    """`MainState` is a TypedDict — its annotations define the contract.

    Any field added or renamed here is a breaking change to the engine
    contract and the WebSocket payload contract.
    """
    annotations = MainState.__annotations__
    for required in ("messages", "input", "response", "expression", "motion", "session_id"):
        assert required in annotations, f"MainState missing field: {required}"


def test_personality_type_is_six_values() -> None:
    """The personality literal must list exactly six options.

    The CLI wizard, the personality manager, and the persona prompt
    files all key off this list. Adding a personality means editing
    `PERSONALITY_DESCRIPTIONS` AND shipping a new `.txt` file AND
    extending `PERSONALITY_TYPE`.
    """
    args = getattr(PERSONALITY_TYPE, "__args__", ())
    assert len(args) == 6
    for required in ("caring", "tsundere", "genki", "kuudere", "yandere", "dandere"):
        assert required in args
