"""Tests for the Composio tool loader.

No real Composio calls — a fake client stands in, and the global
registry is snapshotted/restored around every test.
"""

from __future__ import annotations

import pytest
from langchain_core.tools import tool

from yumii.tools import composio_loader
from yumii.tools.policy import ToolCategory
from yumii.tools.registry import registry

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def preserved_registry():
    tools = dict(registry._tools)
    policies = dict(registry._policies)
    loaded = set(composio_loader._registered_composio_tools)
    composio_loader._registered_composio_tools.clear()
    yield
    registry._tools.clear()
    registry._policies.clear()
    registry._tools.update(tools)
    registry._policies.update(policies)
    composio_loader._registered_composio_tools.clear()
    composio_loader._registered_composio_tools.update(loaded)


@tool
def gmail_fetch_emails(count: int) -> str:
    """Fetch recent emails."""
    return "emails"


@tool
def gmail_send_email(to: str) -> str:
    """Send an email."""
    return "sent"


class FakeTools:
    def __init__(self, tools=None, exc=None):
        self._tools, self._exc = tools or [], exc

    def get(self, user_id, tools=None, toolkits=None, limit=None):
        if self._exc:
            raise self._exc
        return self._tools


class FakeClient:
    def __init__(self, tools=None, exc=None):
        self.tools = FakeTools(tools, exc)


async def test_no_key_is_a_noop(monkeypatch):
    monkeypatch.setattr(composio_loader, "composio_api_key", lambda: None)
    before = len(registry)
    assert await composio_loader.load_and_register_composio_tools() == []
    assert len(registry) == before


async def test_no_toolkits_is_a_noop(monkeypatch):
    monkeypatch.setattr(composio_loader, "composio_api_key", lambda: "ak_test")
    monkeypatch.setattr(composio_loader, "enabled_toolkits", lambda: [])
    assert await composio_loader.load_and_register_composio_tools() == []


async def test_registers_tools_with_gated_external_policy(monkeypatch):
    monkeypatch.setattr(composio_loader, "composio_api_key", lambda: "ak_test")
    monkeypatch.setattr(composio_loader, "enabled_toolkits", lambda: ["GMAIL"])
    factory = lambda: FakeClient(tools=[gmail_fetch_emails, gmail_send_email])  # noqa: E731

    names = await composio_loader.load_and_register_composio_tools(client_factory=factory)

    assert names == ["gmail_fetch_emails", "gmail_send_email"]
    policy = registry.get_policy("gmail_send_email")
    assert policy.category is ToolCategory.EXTERNAL
    assert policy.requires_confirmation is True


async def test_collision_is_skipped(monkeypatch):
    registry.register(gmail_fetch_emails)
    monkeypatch.setattr(composio_loader, "composio_api_key", lambda: "ak_test")
    monkeypatch.setattr(composio_loader, "enabled_toolkits", lambda: ["GMAIL"])
    factory = lambda: FakeClient(tools=[gmail_fetch_emails, gmail_send_email])  # noqa: E731

    names = await composio_loader.load_and_register_composio_tools(client_factory=factory)
    assert names == ["gmail_send_email"]


async def test_sdk_failure_never_raises(monkeypatch):
    monkeypatch.setattr(composio_loader, "composio_api_key", lambda: "ak_test")
    monkeypatch.setattr(composio_loader, "enabled_toolkits", lambda: ["GMAIL"])
    factory = lambda: FakeClient(exc=RuntimeError("401 Invalid API key"))  # noqa: E731

    assert await composio_loader.load_and_register_composio_tools(client_factory=factory) == []


async def test_reload_replaces_previous_composio_tools(monkeypatch):
    """A second load (dashboard hot-reload) swaps the tool set cleanly."""
    monkeypatch.setattr(composio_loader, "composio_api_key", lambda: "ak_test")
    monkeypatch.setattr(composio_loader, "enabled_toolkits", lambda: ["GMAIL"])

    first = lambda: FakeClient(tools=[gmail_fetch_emails, gmail_send_email])  # noqa: E731
    names = await composio_loader.load_and_register_composio_tools(client_factory=first)
    assert set(names) == {"gmail_fetch_emails", "gmail_send_email"}

    second = lambda: FakeClient(tools=[gmail_fetch_emails])  # noqa: E731
    names = await composio_loader.load_and_register_composio_tools(client_factory=second)
    assert names == ["gmail_fetch_emails"]
    # The tool dropped from the toolkit is gone from the registry too.
    assert "gmail_send_email" not in registry
    assert "gmail_fetch_emails" in registry


async def test_reload_after_disable_drops_all_composio_tools(monkeypatch):
    monkeypatch.setattr(composio_loader, "composio_api_key", lambda: "ak_test")
    monkeypatch.setattr(composio_loader, "enabled_toolkits", lambda: ["GMAIL"])
    factory = lambda: FakeClient(tools=[gmail_fetch_emails])  # noqa: E731
    await composio_loader.load_and_register_composio_tools(client_factory=factory)
    assert "gmail_fetch_emails" in registry

    # User disabled the toolkit — reload with nothing enabled.
    monkeypatch.setattr(composio_loader, "enabled_toolkits", lambda: [])
    names = await composio_loader.load_and_register_composio_tools(client_factory=factory)
    assert names == []
    assert "gmail_fetch_emails" not in registry


def test_enabled_toolkits_normalises(monkeypatch):
    monkeypatch.setattr(
        composio_loader,
        "load_global_config",
        lambda: {"COMPOSIO_TOOLKITS": ["gmail", "  ", 42, "Notion"]},
    )
    assert composio_loader.enabled_toolkits() == ["GMAIL", "NOTION"]


def test_enabled_toolkits_handles_bad_shape(monkeypatch):
    monkeypatch.setattr(
        composio_loader, "load_global_config", lambda: {"COMPOSIO_TOOLKITS": "GMAIL"}
    )
    assert composio_loader.enabled_toolkits() == []
