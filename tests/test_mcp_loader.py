"""Tests for the MCP tool loader.

No real MCP servers are spawned — a fake client factory stands in, and
the global registry is snapshotted/restored around every test.
"""

from __future__ import annotations

import asyncio

import pytest
from langchain_core.tools import tool

from yumii.tools import mcp_loader
from yumii.tools.mcp_config import MCPServerConfig
from yumii.tools.policy import ToolCategory
from yumii.tools.registry import registry

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def preserved_registry():
    """Snapshot the global registry and restore it after each test."""
    tools = dict(registry._tools)
    policies = dict(registry._policies)
    yield
    registry._tools.clear()
    registry._policies.clear()
    registry._tools.update(tools)
    registry._policies.update(policies)


@tool
def fake_calendar_lookup(day: str) -> str:
    """Look up calendar events for a day."""
    return f"events for {day}"


@tool
def fake_note_search(query: str) -> str:
    """Search notes."""
    return f"notes about {query}"


def _server(name: str = "probe") -> MCPServerConfig:
    return MCPServerConfig(name=name, command="whatever", args=())


class FakeClient:
    def __init__(self, tools=None, exc: Exception | None = None, delay: float = 0.0):
        self._tools = tools or []
        self._exc = exc
        self._delay = delay

    async def get_tools(self):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._exc:
            raise self._exc
        return self._tools


async def test_registers_tools_with_gated_external_policy(monkeypatch):
    monkeypatch.setattr(mcp_loader, "load_mcp_servers", lambda: [_server()])
    factory = lambda conns: FakeClient(tools=[fake_calendar_lookup, fake_note_search])  # noqa: E731

    names = await mcp_loader.load_and_register_mcp_tools(client_factory=factory)

    assert names == ["fake_calendar_lookup", "fake_note_search"]
    policy = registry.get_policy("fake_calendar_lookup")
    assert policy.category is ToolCategory.EXTERNAL
    assert policy.requires_confirmation is True


async def test_collision_with_existing_tool_is_skipped(monkeypatch):
    registry.register(fake_calendar_lookup)  # pre-existing native tool
    monkeypatch.setattr(mcp_loader, "load_mcp_servers", lambda: [_server()])
    factory = lambda conns: FakeClient(tools=[fake_calendar_lookup, fake_note_search])  # noqa: E731

    names = await mcp_loader.load_and_register_mcp_tools(client_factory=factory)

    assert names == ["fake_note_search"]
    # the pre-existing registration (default READ policy) is untouched
    assert registry.get_policy("fake_calendar_lookup").category is ToolCategory.READ


async def test_dead_server_is_skipped_without_raising(monkeypatch):
    monkeypatch.setattr(
        mcp_loader, "load_mcp_servers", lambda: [_server("dead"), _server("alive")]
    )
    clients = {
        "dead": FakeClient(exc=RuntimeError("connection refused")),
        "alive": FakeClient(tools=[fake_note_search]),
    }
    factory = lambda conns: clients[next(iter(conns))]  # noqa: E731

    names = await mcp_loader.load_and_register_mcp_tools(client_factory=factory)

    assert names == ["fake_note_search"]


async def test_hung_server_times_out(monkeypatch):
    monkeypatch.setattr(mcp_loader, "load_mcp_servers", lambda: [_server("hung")])
    monkeypatch.setattr(mcp_loader, "_CONNECT_TIMEOUT_SEC", 0.05)
    factory = lambda conns: FakeClient(tools=[fake_note_search], delay=1.0)  # noqa: E731

    names = await mcp_loader.load_and_register_mcp_tools(client_factory=factory)

    assert names == []


async def test_no_servers_configured_is_a_noop(monkeypatch):
    monkeypatch.setattr(mcp_loader, "load_mcp_servers", lambda: [])
    before = len(registry)
    names = await mcp_loader.load_and_register_mcp_tools()
    assert names == []
    assert len(registry) == before
