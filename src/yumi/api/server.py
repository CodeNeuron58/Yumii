"""FastAPI server for the Yumi backend.

Provides a WebSocket endpoint for real-time communication and serves the
Live2D frontend assets.
"""

import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from yumi.core.engine import YumiEngine

# The Engine handles all the heavy lifting: STT, LLM, TTS, and state
engine = YumiEngine()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[Any, None]:
    """Manage the lifecycle of the FastAPI application.

    Initializes the background audio and reasoning tasks on startup.
    """
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


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Handle real-time audio and event communication via WebSocket.

    Processes incoming binary audio chunks and maintains connection state.
    """
    await websocket.accept()
    engine.active_connections.append(websocket)
    try:
        while True:
            message = await websocket.receive()
            if "bytes" in message:
                # Binary audio chunk from the browser
                await engine.audio_input_queue.put(message["bytes"])
    except WebSocketDisconnect:
        if websocket in engine.active_connections:
            engine.active_connections.remove(websocket)


# Mount frontend
# Webui is bundled inside the package at src/yumi/assets/webui/
# __file__ = .../yumi/api/server.py
# .parent       = .../yumi/api/
# .parent.parent = .../yumi/        (package root)
_pkg_dir = Path(__file__).parent.parent
webui_dir = str(_pkg_dir / "assets" / "webui")

# Avatar: user-provided Live2D model files.
# Priority order:
#   1. ~/.yumi/avatar/      (recommended for installed packages)
#   2. <repo-root>/assets/avatar/  (legacy, for git-clone development use)
def _find_avatar_dir() -> str | None:
    candidates = [
        Path.home() / ".yumi" / "avatar",
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
    app.mount("/Yumi_Avatar", StaticFiles(directory=avatar_dir), name="avatar")
app.mount("/", StaticFiles(directory=webui_dir, html=True), name="static")
