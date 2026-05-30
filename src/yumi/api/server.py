import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from yumi.core.engine import YumiEngine

# ---------------------------------------------------------------------------
# Application Setup
# ---------------------------------------------------------------------------

# The Engine handles all the heavy lifting: STT, LLM, TTS, and state
engine = YumiEngine()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage the lifecycle of the FastAPI application.
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
    """
    Main WebSocket endpoint for real-time audio and event communication.
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
# Path logic: src/yumi/api/server.py -> src/yumi/api -> src/yumi -> src -> root
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
webui_dir = os.path.join(root_dir, "assets", "webui")
avatar_dir = os.path.join(root_dir, "assets", "avatar")

app.mount("/Yumi_Avatar", StaticFiles(directory=avatar_dir), name="avatar")
app.mount("/", StaticFiles(directory=webui_dir, html=True), name="static")
