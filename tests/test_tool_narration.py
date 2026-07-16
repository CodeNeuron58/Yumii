"""Tool-call narration — no more dead air while tools run.

When an agent pass ends in tool calls, the engine speaks the model's
accompanying narration immediately (or a short filler if the model
stayed silent), so the user hears voice during the seconds a tool
takes instead of silence.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from yumii.core.engine import _TOOL_NARRATION_FILLERS, _derive_tool_narration


def _tool_pass(content: str) -> dict:
    """Shape of agent_node's output for a pass that calls tools."""
    return {
        "messages": [
            HumanMessage(content="check my email"),
            AIMessage(
                content=content,
                tool_calls=[{"name": "GMAIL_FETCH_EMAILS", "args": {}, "id": "c1"}],
            ),
        ]
    }


def test_model_narration_is_spoken():
    out = _tool_pass("Give me a second, peeking at your inbox.")
    assert _derive_tool_narration(out) == "Give me a second, peeking at your inbox."


def test_think_blocks_never_reach_tts():
    out = _tool_pass("<think>user wants email, call fetch</think>Let me look.")
    assert _derive_tool_narration(out) == "Let me look."


def test_silent_tool_call_gets_a_filler():
    assert _derive_tool_narration(_tool_pass("")) in _TOOL_NARRATION_FILLERS


def test_think_only_content_gets_a_filler():
    out = _tool_pass("<think>no words for the user</think>")
    assert _derive_tool_narration(out) in _TOOL_NARRATION_FILLERS


def test_no_filler_after_the_first_pass():
    """Chained silent tool passes must not chant 'on it… one moment…'."""
    out = _tool_pass("")
    assert _derive_tool_narration(out, allow_filler=False) is None


def test_model_words_still_spoken_on_later_passes():
    out = _tool_pass("Now checking your calendar too.")
    assert (
        _derive_tool_narration(out, allow_filler=False)
        == "Now checking your calendar too."
    )


def test_final_pass_is_not_narrated():
    # The final pass carries "response" — the real reply speaks instead.
    out = {
        "messages": [AIMessage(content="Here are your emails!")],
        "response": "Here are your emails!",
    }
    assert _derive_tool_narration(out) is None


def test_pass_without_tool_calls_is_not_narrated():
    out = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello!")]}
    assert _derive_tool_narration(out) is None


def test_tool_message_after_ai_does_not_confuse_detection():
    # Defensive: last message may be a ToolMessage in odd shapes; the
    # detector looks for the most recent AIMessage.
    out = _tool_pass("Checking now.")
    out["messages"].append(
        ToolMessage(content="result", tool_call_id="c1", name="GMAIL_FETCH_EMAILS")
    )
    assert _derive_tool_narration(out) == "Checking now."


def test_garbage_inputs_return_none():
    assert _derive_tool_narration(None) is None
    assert _derive_tool_narration("not-a-dict") is None
    assert _derive_tool_narration({}) is None
    assert _derive_tool_narration({"messages": []}) is None
