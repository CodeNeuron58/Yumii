"""Smoke tests for module-level imports.

These tests do not run any business logic. They just verify that the
top-level modules of the engine and API import without raising. A
broken import (a renamed class, a missing dependency, a typo) is
caught here in milliseconds, before any deeper test runs.
"""

import importlib


def test_core_engine_imports():
    """`yumi.core.engine` must import cleanly."""
    module = importlib.import_module("yumi.core.engine")
    assert hasattr(module, "YumiEngine")


def test_api_server_imports():
    """`yumi.api.server` must import cleanly and expose a FastAPI app."""
    module = importlib.import_module("yumi.api.server")
    assert hasattr(module, "app")


def test_agent_graph_imports():
    """`yumi.agent.graph` must import cleanly and expose `build_graph`."""
    module = importlib.import_module("yumi.agent.graph")
    assert hasattr(module, "build_graph")


def test_agent_llm_imports():
    """`yumi.agent.llm` must import cleanly and expose `get_agent`."""
    module = importlib.import_module("yumi.agent.llm")
    assert hasattr(module, "get_agent")


def test_tts_factory_imports():
    """`yumi.tts.factory` must import cleanly and expose `get_speaker`."""
    module = importlib.import_module("yumi.tts.factory")
    assert hasattr(module, "get_speaker")


def test_audio_pipeline_imports():
    """`yumi.audio.stt` must import cleanly and expose `AudioPipeline`."""
    module = importlib.import_module("yumi.audio.stt")
    assert hasattr(module, "AudioPipeline")


def test_cli_imports():
    """The Typer CLI entry point must import cleanly."""
    module = importlib.import_module("yumi.cli")
    assert hasattr(module, "app")
