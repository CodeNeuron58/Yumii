"""Tests for the two preview blockers:

* the backend picks a free port instead of dying on a taken 8000
* the Host-header allowlist blocks DNS-rebinding into the local API
"""

from __future__ import annotations

import socket

import pytest


# ── Free-port selection ────────────────────────────────────────────────


def test_pick_free_port_returns_a_bindable_port():
    from yumii.cli import _pick_free_port

    port = _pick_free_port()
    # Whatever it returns must actually be free right now.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))  # must not raise
    finally:
        s.close()


def test_pick_free_port_skips_a_taken_port():
    from yumii.cli import _PORT_BASE, _pick_free_port

    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        try:
            blocker.bind(("127.0.0.1", _PORT_BASE))
            blocker.listen(1)
        except OSError:
            pytest.skip(f"port {_PORT_BASE} already in use in this environment")
        port = _pick_free_port()
        assert port != _PORT_BASE
        assert _PORT_BASE < port < _PORT_BASE + 12
    finally:
        blocker.close()


def test_write_port_file(tmp_path, monkeypatch):
    import pathlib

    from yumii import cli

    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
    cli._write_port_file(8003)
    assert (tmp_path / ".yumii" / "backend.port").read_text() == "8003"


# ── Host-header allowlist (DNS-rebinding guard) ────────────────────────


def test_allowed_hosts_are_loopback_only():
    from yumii.api.server import _ALLOWED_HOSTS

    assert "127.0.0.1" in _ALLOWED_HOSTS
    assert "localhost" in _ALLOWED_HOSTS
    assert "*" not in _ALLOWED_HOSTS  # never a wildcard


def test_trustedhost_rejects_rebinding_host():
    from fastapi import FastAPI
    from starlette.middleware.trustedhost import TrustedHostMiddleware
    from starlette.testclient import TestClient

    from yumii.api.server import _ALLOWED_HOSTS

    app = FastAPI()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_ALLOWED_HOSTS)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    client = TestClient(app)
    # Legitimate loopback host (any port) is allowed.
    assert client.get("/ping", headers={"host": "127.0.0.1:8000"}).status_code == 200
    assert client.get("/ping", headers={"host": "localhost:8005"}).status_code == 200
    # A rebinding attacker's domain that resolves to 127.0.0.1 is rejected.
    assert client.get("/ping", headers={"host": "evil.com"}).status_code == 400
    assert client.get("/ping", headers={"host": "attacker.example:8000"}).status_code == 400
