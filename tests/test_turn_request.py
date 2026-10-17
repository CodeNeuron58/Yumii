"""What the model sees on each agent pass of a turn.

Every pass after a tool call used to re-append the user's question after
the tool results — [..., Human, AI(tool_call), Tool, Human(same)] — which
models read as a fresh request and answer by calling the tool again.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from yumii.agent import graph
from yumii.agent.graph import _turn_request, agent_node


def _past(n: int) -> list:
    """n prior exchanges (2 messages each) from earlier turns."""
    out: list = []
    for i in range(n):
        out += [HumanMessage(content=f"old {i}", id=f"hum_old{i}"), AIMessage(content=f"reply {i}", id=f"ai_old{i}")]
    return out


def _tool_pass(turn: str, k: int) -> list:
    call_id = f"call_{turn}_{k}"
    return [
        AIMessage(content="", id=f"ai_{turn}_{k}", tool_calls=[{"name": "get_current_time", "args": {}, "id": call_id}]),
        ToolMessage(content="12:00", tool_call_id=call_id, name="get_current_time", id=f"tool_{turn}_{k}"),
    ]


def _humans(messages: list) -> list[str]:
    return [m.content for m in messages if isinstance(m, HumanMessage)]


def test_first_pass_puts_the_question_last():
    question = HumanMessage(content="what time is it", id="hum_T")

    msgs = _turn_request(_past(2), question)

    assert msgs[-1] is question
    assert _humans(msgs) == ["old 0", "old 1", "what time is it"]


def test_after_tools_the_question_is_not_repeated():
    question = HumanMessage(content="what time is it", id="hum_T")
    history = _past(2) + [question] + _tool_pass("T", 0)

    msgs = _turn_request(history, question)

    assert _humans(msgs).count("what time is it") == 1
    assert isinstance(msgs[-1], ToolMessage)  # the model answers the tool result
    assert [type(m) for m in msgs[-3:]] == [HumanMessage, AIMessage, ToolMessage]


def test_a_long_tool_chain_never_windows_away_this_turn(monkeypatch):
    """Groq's 12-message window must trim the PAST, not this turn's question."""
    monkeypatch.setattr(graph, "_request_budgets", lambda: (3000, 12))
    question = HumanMessage(content="check my mail", id="hum_T")
    current = [question]
    for k in range(6):  # 13 messages this turn — more than the whole window
        current += _tool_pass("T", k)
    history = _past(10) + current

    msgs = _turn_request(history, question)

    assert msgs[: -len(current)] == []  # no room left for the past
    assert msgs[-len(current):] == current  # but the turn survives whole
    assert _humans(msgs) == ["check my mail"]


def test_the_window_still_fits_past_plus_turn(monkeypatch):
    monkeypatch.setattr(graph, "_request_budgets", lambda: (3000, 12))
    question = HumanMessage(content="what time is it", id="hum_T")
    current = [question] + _tool_pass("T", 0)
    history = _past(10) + current

    msgs = _turn_request(history, question)

    assert len(msgs) == 12
    assert msgs[-3:] == current


class _RecordingLLM:
    def __init__(self, replies: list[AIMessage]):
        self.replies = list(replies)
        self.requests: list[list] = []

    async def ainvoke(self, messages):
        self.requests.append(list(messages))
        return self.replies.pop(0)


@pytest.mark.asyncio
async def test_agent_node_second_pass_sees_the_question_once(monkeypatch):
    llm = _RecordingLLM([AIMessage(content="It's noon.", id="ai_final")])
    monkeypatch.setattr(graph, "get_agent_llm", lambda **kw: llm)
    question = HumanMessage(content="what time is it", id="hum_T")
    state = {
        "input": "what time is it",
        "turn_id": "T",
        "messages": _past(1) + [question] + _tool_pass("T", 0),
        "session_id": "s1",
    }

    out = await agent_node(state)

    sent = llm.requests[0]
    assert _humans(sent).count("what time is it") == 1
    assert isinstance(sent[-1], ToolMessage)
    assert out["response"]  # the final pass still synthesizes a reply
