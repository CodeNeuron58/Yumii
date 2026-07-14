"""Tests for the tool registry, policy dataclass, and time tool.

These tests cover the foundation that PR 2 (custom StateGraph with
``bind_tools`` + ``ToolNode``) and PR 4 (HITL confirmation gates) will
build on top of.
"""

from __future__ import annotations

import pytest
from langchain_core.tools import tool

from yumii.tools import policy as policy_mod
from yumii.tools.policy import ToolCategory, ToolPolicy
from yumii.tools.registry import ToolRegistry, registry as global_registry
from yumii.tools.time_tool import TimeInput, get_current_time


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


@pytest.fixture
def fresh_registry() -> ToolRegistry:
    """Return a clean ``ToolRegistry`` instance for each test."""
    return ToolRegistry()


@pytest.fixture(autouse=True)
def _clear_global_registry():
    """Reset the module-level singleton between tests.

    Several tests register on the global ``registry``; without this
    fixture they would leak state into each other. We also re-import
    :mod:`yumii.tools.time_tool` so its module-level registration
    side effect fires again — pytest's import cache means a plain
    ``import time_tool`` inside a test would be a no-op.
    """
    global_registry.clear()
    # Re-run the module-level registration side effect. Using
    # ``importlib.reload`` bypasses the module cache and re-executes
    # the top-level code, including the ``register(...)`` call.
    import importlib

    import yumii.tools.time_tool  # noqa: F401

    importlib.reload(yumii.tools.time_tool)
    yield
    global_registry.clear()


# ----------------------------------------------------------------------
# ToolPolicy
# ----------------------------------------------------------------------


def test_default_policy_for_read_has_no_confirmation() -> None:
    """READ tools should not require a confirmation gate by default."""
    p = policy_mod.default_policy_for(ToolCategory.READ)
    assert p.requires_confirmation is False
    assert p.category is ToolCategory.READ


def test_default_policy_for_external_requires_confirmation() -> None:
    """EXTERNAL tools should require a confirmation gate by default."""
    p = policy_mod.default_policy_for(ToolCategory.EXTERNAL)
    assert p.requires_confirmation is True
    assert p.category is ToolCategory.EXTERNAL


def test_tool_policy_is_frozen() -> None:
    """ToolPolicy is a frozen dataclass — assignment should raise."""
    p = ToolPolicy()
    with pytest.raises((AttributeError, TypeError)):
        p.requires_confirmation = True  # type: ignore[misc]


# ----------------------------------------------------------------------
# ToolRegistry basics
# ----------------------------------------------------------------------


@tool
def _sample_tool(x: int) -> int:
    """A trivial sample tool for registry tests."""
    return x * 2


def test_register_and_get_roundtrip(fresh_registry: ToolRegistry) -> None:
    """A registered tool should be retrievable by name."""
    fresh_registry.register(_sample_tool)
    assert fresh_registry.get(_sample_tool.name) is _sample_tool


def test_register_default_policy_is_read(fresh_registry: ToolRegistry) -> None:
    """Tools registered without a policy should default to READ, no confirmation."""
    fresh_registry.register(_sample_tool)
    policy = fresh_registry.get_policy(_sample_tool.name)
    assert policy.category is ToolCategory.READ
    assert policy.requires_confirmation is False


def test_register_with_explicit_policy(fresh_registry: ToolRegistry) -> None:
    """A tool registered with an explicit policy should expose it via ``get_policy``."""
    p = ToolPolicy(
        category=ToolCategory.EXTERNAL,
        requires_confirmation=True,
        idempotency_key="weather_lookup",
    )
    fresh_registry.register(_sample_tool, p)
    assert fresh_registry.get_policy(_sample_tool.name) is p


def test_register_duplicate_raises(fresh_registry: ToolRegistry) -> None:
    """Re-registering a name without ``overwrite`` should raise ``ValueError``."""
    fresh_registry.register(_sample_tool)
    with pytest.raises(ValueError, match="already registered"):
        fresh_registry.register(_sample_tool)


def test_register_duplicate_with_overwrite_succeeds(fresh_registry: ToolRegistry) -> None:
    """``overwrite=True`` should let tests swap tools in and out."""
    fresh_registry.register(_sample_tool)
    fresh_registry.register(_sample_tool, overwrite=True)  # no raise
    assert fresh_registry.get(_sample_tool.name) is _sample_tool


def test_unregister_removes_tool_and_policy(fresh_registry: ToolRegistry) -> None:
    """``unregister`` should drop the tool; re-registering then works."""
    fresh_registry.register(_sample_tool)
    fresh_registry.unregister(_sample_tool.name)
    assert _sample_tool.name not in fresh_registry
    fresh_registry.register(_sample_tool)  # no ValueError — really gone
    assert _sample_tool.name in fresh_registry


def test_unregister_unknown_name_is_a_noop(fresh_registry: ToolRegistry) -> None:
    fresh_registry.unregister("never-registered")  # must not raise


def test_get_unknown_tool_raises(fresh_registry: ToolRegistry) -> None:
    """``get`` for an unknown name should raise ``KeyError`` with a useful message."""
    with pytest.raises(KeyError, match="No tool named"):
        fresh_registry.get("does_not_exist")


def test_tools_requiring_confirmation_filters(fresh_registry: ToolRegistry) -> None:
    """Only tools whose policy says so should appear in the confirmation list."""

    @tool
    def local_tool() -> str:
        """A local tool with no side effects."""
        return "local"

    @tool
    def external_tool() -> str:
        """A tool that talks to a third-party."""
        return "external"

    fresh_registry.register(local_tool)  # default READ → no confirmation
    fresh_registry.register(
        external_tool,
        ToolPolicy(category=ToolCategory.EXTERNAL, requires_confirmation=True),
    )
    assert fresh_registry.tools_requiring_confirmation() == [external_tool.name]


# ----------------------------------------------------------------------
# Module-level singleton
# ----------------------------------------------------------------------


def test_module_level_registry_exposes_time_tool() -> None:
    """Importing ``yumii.tools.time_tool`` should auto-register on the singleton."""
    # Importing the module triggers registration as a side effect.
    from yumii.tools import time_tool  # noqa: F401

    assert "get_current_time" in global_registry
    p = global_registry.get_policy("get_current_time")
    assert p.category is ToolCategory.READ
    assert p.requires_confirmation is False


def test_time_tool_has_args_schema() -> None:
    """The refactored ``get_current_time`` tool should expose ``TimeInput`` as args_schema."""
    assert get_current_time.args_schema is TimeInput


def test_time_tool_default_tz_returns_local_time() -> None:
    """``get_current_time()`` with no arg should return a non-empty time string."""
    out = get_current_time.invoke({})
    assert isinstance(out, str)
    # "HH:MM AM/PM" — 8 chars including AM/PM, e.g. "03:42 PM"
    assert len(out) >= 7


def test_time_tool_unknown_tz_returns_error_string() -> None:
    """An unknown IANA timezone name should yield a graceful error, not raise."""
    out = get_current_time.invoke({"tz": "Not/A/Real_Zone"})
    assert "Unknown timezone" in out
