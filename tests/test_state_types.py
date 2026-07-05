"""Tests for the core state types."""

from yumii.core.types import PERSONALITY_TYPE


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
