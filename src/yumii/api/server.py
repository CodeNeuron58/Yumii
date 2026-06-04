"""FastAPI server for the Yumii backend.

Provides WebSocket real-time communication, REST endpoints for session
management, and serves the Live2D frontend assets.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState

from yumii.core.engine import YumiiEngine
from yumii.core.global_config import load_global_config
from yumii.core.session_manager import SessionRow, session_manager

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


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    await websocket.accept()

    # --- Phase 1: Session negotiation ---
    # Try to read the client's first message.  If it's a session_select
    # JSON payload we honour it; otherwise default to a new session.
    session_id: str | None = None
    try:
        first_msg = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
        data = json.loads(first_msg)
    except Exception:
        data = {}

    if data.get("type") == "session_select":
        action = data.get("action", "new")
        if action == "new":
            session_id = await engine.create_new_session()
        elif action == "resume":
            sid = data.get("session_id", "")
            session_id = await engine.resume_session(sid)
        else:
            session_id = await engine.create_new_session()
    else:
        # Default: brand new session
        session_id = await engine.create_new_session()

    # Take-over: if another connection is active, politely evict it.
    for conn in engine.active_connections:
        if conn != websocket and conn.client_state == WebSocketState.CONNECTED:
            try:
                await conn.send_text(
                    json.dumps({"type": "session_taken_over"})
                )
                await conn.close()
            except Exception:
                pass
    engine.active_connections = [websocket]

    # Notify client that session is ready
    await websocket.send_text(
        json.dumps(
            {
                "type": "session_ready",
                "session_id": session_id,
                "session_name": engine.active_session_name,
            }
        )
    )

    # --- Phase 2: Normal audio / command loop ---
    try:
        while True:
            message = await websocket.receive()

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

                    elif msg_type == "rename_session":
                        name = payload.get("name", "").strip()
                        if engine.active_session_id and name:
                            await session_manager.rename_session(
                                engine.active_session_id, name
                            )
                            engine.active_session_name = name
                            await engine.broadcast_payload(
                                {
                                    "type": "session_renamed",
                                    "session_id": engine.active_session_id,
                                    "session_name": name,
                                }
                            )

                    elif msg_type == "forget_me":
                        from yumii.core.memory_manager import memory_manager

                        await memory_manager.clear_all_facts()
                        # Also wipe checkpoints?  No — just facts for now.
                        await engine.broadcast_payload(
                            {"type": "memory_cleared"}
                        )

                except Exception:
                    pass
                continue

            # Binary audio chunk from the browser
            if "bytes" in message:
                await engine.audio_input_queue.put(message["bytes"])

    except WebSocketDisconnect:
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
