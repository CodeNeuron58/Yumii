"""Reasoning-model safety: <think> blocks must never reach TTS.

Reasoning models (minimax-m3, qwen, deepseek-r1, …) normally return
chain-of-thought in a separate field, but some provider/model combos
inline it as <think>…</think> in the content — which the orb would
otherwise speak aloud.
"""

from __future__ import annotations

from yumii.agent.synthesizer import synthesize


def test_think_block_is_stripped():
    out = synthesize("<think>The user wants email. I should call the tool.</think>Here are your emails!")
    assert out.response_text == "Here are your emails!"


def test_thinking_tag_variant_is_stripped():
    out = synthesize("<thinking>hmm</thinking>Sure thing.")
    assert out.response_text == "Sure thing."


def test_multiline_think_block_is_stripped():
    text = "<think>\nstep 1\nstep 2\n</think>\nAll done, three emails found."
    assert synthesize(text).response_text == "All done, three emails found."


def test_think_only_content_degrades_to_placeholder():
    out = synthesize("<think>never finished the answer</think>")
    assert out.response_text == "..."
    assert out.expression == "normal"


def test_normal_text_untouched():
    assert synthesize("Hi there!").response_text == "Hi there!"
