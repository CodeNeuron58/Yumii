"""FastAPI server for the Yumii backend.

Provides WebSocket real-time communication, REST endpoints for session
management, and serves the Live2D frontend assets.
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState

from yumii.core.engine import YumiiEngine
from yumii.core.global_config import load_global_config
from yumii.core.logging import get_logger
from yumii.core.memory_manager import UserFact, memory_manager
from yumii.core.session_manager import SessionRow, session_manager

log = get_logger(__name__)

# The Engine handles all the heavy lifting: STT, LLM, TTS, and state
engine = YumiiEngine()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[Any, None]:
    """Manage the lifecycle of the FastAPI application.

    Initializes the background audio and reasoning tasks on startup.
    """
    await engine.initialize()

    # Spawn the three parallel engines in the background
    asyncio.create_task(engine.audio_listener_task())
    asyncio.create_task(engine.reasoning_engine_task())
    asyncio.create_task(engine.tts_speaker_task())
    yield
    # --- shutdown ---
    await engine.shutdown()


app = FastAPI(lifespan=lifespan)

# Only our own frontends may call this API from a browser context:
# the served orb page (localhost:8000) and the Tauri webview. A
# wildcard here would let any website the user visits read their
# facts and sessions off 127.0.0.1 — this API holds personal memory.
_ALLOWED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    # Packaged Tauri webview origins (platform-dependent).
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
    # `tauri dev` serves frontendDist from its own local static server
    # (default port 1430) — the webview's origin in development.
    "http://127.0.0.1:1430",
    "http://localhost:1430",
]
# Escape hatch for nonstandard setups (e.g. a custom Tauri dev port):
# comma-separated origins appended to the allowlist.
_ALLOWED_ORIGINS += [
    o.strip()
    for o in os.environ.get("YUMII_ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _log_foreign_origins(request, call_next):
    """Surface requests from origins outside the allowlist.

    CORS failures are invisible server-side (the browser blocks the
    *response*), so without this a legitimate frontend blocked by a
    missing allowlist entry just polls forever with no clue in the logs.
    """
    origin = request.headers.get("origin")
    if origin and origin not in _ALLOWED_ORIGINS:
        log.warning(
            "http_origin_not_allowlisted", origin=origin, path=request.url.path
        )
    return await call_next(request)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe. The desktop shell polls this before connecting the
    WebSocket so it can show a 'waking up…' state while the brain boots."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# REST API: Sessions
# ---------------------------------------------------------------------------


@app.get("/api/sessions")
async def list_sessions() -> list[dict[str, Any]]:
    """Return the list of non-archived sessions, most recent first."""
    rows: list[SessionRow] = await session_manager.list_sessions()
    return [
        {
            "id": r.id,
            "name": r.name,
            "created_at": r.created_at,
            "last_active_at": r.last_active_at,
            "message_count": r.message_count,
        }
        for r in rows
    ]


@app.post("/api/sessions")
async def create_session(name: str | None = None) -> dict[str, Any]:
    """Create a brand-new session and return its metadata."""
    session_id = await engine.create_new_session(name=name)
    return {
        "session_id": session_id,
        "name": engine.active_session_name,
    }


@app.post("/api/sessions/{session_id}/resume")
async def resume_session_endpoint(session_id: str) -> dict[str, Any]:
    """Resume an existing session by ID."""
    sid = await engine.resume_session(session_id)
    return {
        "session_id": sid,
        "name": engine.active_session_name,
    }


@app.delete("/api/sessions/{session_id}")
async def delete_session_endpoint(session_id: str) -> dict[str, Any]:
    """Hard-delete a session and its summary."""
    await session_manager.delete_session(session_id)
    return {"deleted": True, "session_id": session_id}


# ---------------------------------------------------------------------------
# REST API: Facts (Long-term Memory)
# ---------------------------------------------------------------------------


@app.get("/api/facts")
async def list_facts() -> list[dict[str, Any]]:
    """Return all stored user facts."""
    facts: list[UserFact] = await memory_manager.get_facts(limit=500)
    return [
        {
            "id": f.id,
            "fact": f.fact,
            "category": f.category,
            "confidence": f.confidence,
            "created_at": f.created_at,
        }
        for f in facts
    ]


@app.put("/api/facts/{fact_id}")
async def update_fact_endpoint(fact_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Update the text of an existing fact."""
    new_text = body.get("fact", "").strip()
    if not new_text:
        raise HTTPException(status_code=400, detail="Missing 'fact' field")
    await memory_manager.update_fact(fact_id, new_text)
    return {"updated": True, "fact_id": fact_id}


@app.delete("/api/facts/{fact_id}")
async def delete_fact_endpoint(fact_id: str) -> dict[str, Any]:
    """Delete a single fact."""
    await memory_manager.delete_fact(fact_id)
    return {"deleted": True, "fact_id": fact_id}


# ---------------------------------------------------------------------------
# REST API: Config
# ---------------------------------------------------------------------------


@app.get("/api/config")
async def get_config() -> dict[str, Any]:
    """Return runtime configuration useful for the frontend."""
    config = load_global_config()
    personality = config.get("PERSONALITY", "caring")

    # Resolve avatar path
    avatar_dir = _find_avatar_dir()
    model_url = None
    if avatar_dir:
        # Try to find the first .model3.json file
        avatar_path = Path(avatar_dir)
        for candidate in avatar_path.iterdir():
            if candidate.suffix == ".json" and "model3" in candidate.name:
                model_url = f"/Yumii_Avatar/{candidate.name}"
                break

    return {
        "personality": personality,
        "avatar_url": model_url,
    }


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Handle real-time audio and event communication via WebSocket.

    Protocol:
        1. Client connects.
        2. Server sends ``{"type": "session_list"}`` (or client sends
           ``{"type": "session_select", "action": "new|resume", ...}``).
        3. After session negotiation, normal audio flow begins.
    """
    # Browsers always send an Origin header; reject pages that aren't
    # ours so a malicious website can't stream audio or commands into
    # the engine. Non-browser clients (no Origin) are local tools
    # already running with the user's privileges — allowed.
    origin = websocket.headers.get("origin")
    if origin is not None and origin not in _ALLOWED_ORIGINS:
        log.warning("ws_origin_rejected", origin=origin)
        await websocket.close(code=1008)
        return

    await websocket.accept()

    # --- Phase 1: Session negotiation ---
    # The frontend sends a session_select frame as its very first
    # message (ordered before any mic audio). Legacy clients may lead
    # with binary audio instead — stash those frames and fall through
    # to the default after a short deadline.
    data: dict[str, Any] = {}
    stashed_audio: list[bytes] = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 3.0
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        try:
            message = await asyncio.wait_for(websocket.receive(), timeout=remaining)
        except asyncio.TimeoutError:
            break
        if message.get("type") == "websocket.disconnect":
            return
        if message.get("text") is not None:
            try:
                data = json.loads(message["text"])
            except json.JSONDecodeError:
                data = {}
            break
        if message.get("bytes") is not None:
            stashed_audio.append(message["bytes"])

    action = (
        data.get("action", "auto")
        if data.get("type") == "session_select"
        else "auto"
    )
    if action == "new":
        await engine.create_new_session()
    elif action == "resume":
        # Falls back to a new session if the ID is unknown.
        await engine.resume_session(data.get("session_id", ""))
    elif engine.active_session_id is None:
        # "auto" on a fresh boot — nothing to keep, start a new one.
        await engine.create_new_session()
    # "auto" with an active session: keep it. Reconnects (the frontend
    # retries every 3s) must NOT mint a new session each time.

    # Any audio that raced ahead of the negotiation belongs to this
    # session — feed it through now.
    for chunk in stashed_audio:
        await engine.audio_input_queue.put(chunk)

    # Take-over: if another connection is active, politely evict it.
    for conn in engine.active_connections:
        if conn != websocket and conn.client_state == WebSocketState.CONNECTED:
            try:
                await conn.close()
            except Exception:
                pass
    engine.active_connections = [websocket]

    # --- Phase 2: Normal audio / command loop ---
    try:
        while True:
            message = await websocket.receive()

            # Starlette *returns* the disconnect message rather than
            # raising; calling receive() again after it is a
            # RuntimeError, so break out here.
            if message.get("type") == "websocket.disconnect":
                break

            # JSON text commands from the frontend
            if "text" in message:
                try:
                    payload = json.loads(message["text"])
                    msg_type = payload.get("type", "")

                    if msg_type == "command":
                        cmd = payload.get("command", "")
                        # Inject the command into the transcription queue
                        # so the engine's command handler can process it.
                        await engine.transcription_queue.put(cmd)

                    # PR 4: HITL confirmation reply from the browser.
                    # The engine is awaiting the future registered
                    # under ``request_id``; we just resolve it.
                    elif msg_type == "confirmation_response":
                        request_id = payload.get("request_id", "")
                        approved = bool(payload.get("approve", False))
                        engine.resolve_confirmation(request_id, approved)

                except Exception:
                    pass
                continue

            # Binary audio chunk from the browser
            if "bytes" in message:
                await engine.audio_input_queue.put(message["bytes"])

    except WebSocketDisconnect:
        pass
    finally:
        # Every exit path — clean disconnect, eviction, error — must
        # drop the connection from the broadcast list.
        if websocket in engine.active_connections:
            engine.active_connections.remove(websocket)


# ---------------------------------------------------------------------------
# Static file mounts
# ---------------------------------------------------------------------------

_pkg_dir = Path(__file__).parent.parent
webui_dir = str(_pkg_dir / "assets" / "webui")


def _find_avatar_dir() -> str | None:
    """Resolve the user's Live2D avatar directory."""
    candidates = [
        Path.home() / ".yumii" / "avatar",
        _pkg_dir.parent.parent / "assets" / "avatar",  # repo root fallback
    ]
    for candidate in candidates:
        try:
            if candidate.is_dir() and any(candidate.iterdir()):
                return str(candidate)
        except PermissionError:
            pass
    return None


avatar_dir = _find_avatar_dir()
if avatar_dir:
    app.mount("/Yumii_Avatar", StaticFiles(directory=avatar_dir), name="avatar")
app.mount("/", StaticFiles(directory=webui_dir, html=True), name="static")
