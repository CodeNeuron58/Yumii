import os
import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List

from yumi.agent.graph import build_graph

# Global clients to broadcast to UI
active_connections: List[WebSocket] = []

# Store the main event loop for thread-safe operations
main_loop = None

# --- Background Agent Loop ---
async def agent_loop():
    print("Agent loop started. Waiting 2 seconds for server to boot...")
    await asyncio.sleep(2)
    print("System ready. Listening for speech...")
    
    session_id = "yumi_session_1"
    
    while True:
        try:
            # We run the synchronous graph invocation in a threadpool so it doesn't block the FastAPI async event loop
            # Config with thread_id is required for InMemorySaver checkpointing
            await asyncio.to_thread(
                graph_app.invoke,
                {
                    "input": "",
                    "response": "",
                    "expression": "",
                    "motion": "",
                    "messages": [],
                    "session_id": session_id
                },
                config={"configurable": {"thread_id": session_id}}
            )
        except Exception as e:
            print(f"Agent Loop Error: {e}")
            await asyncio.sleep(1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_loop
    main_loop = asyncio.get_running_loop()
    asyncio.create_task(agent_loop())
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
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)

def sync_broadcast(payload: dict):
    # This function is called synchronously from the LangGraph speak_node thread
    async def broadcast():
        dead_connections = []
        for connection in active_connections:
            try:
                await connection.send_text(json.dumps(payload))
            except Exception as e:
                print(f"WS Send Error: {e}")
                dead_connections.append(connection)
        for dead in dead_connections:
            active_connections.remove(dead)
            
    try:
        if main_loop:
            asyncio.run_coroutine_threadsafe(broadcast(), main_loop)
        else:
            # Fallback if loop is not yet captured (should not happen in production)
            asyncio.run(broadcast())
    except Exception as e:
        print(f"Failed to broadcast WS: {e}")

# Build the global graph application injecting our broadcast callback
graph_app = build_graph(sync_broadcast)

# Mount the static files pointing to the root directory
# This ensures that http://localhost:8000/webui/index.html still resolves to webui/index.html
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
webui_dir = os.path.join(package_root, "webui")
avatar_dir = os.path.join(package_root, "Yumi_Avatar")

app.mount("/Yumi_Avatar", StaticFiles(directory=avatar_dir), name="avatar")
app.mount("/", StaticFiles(directory=webui_dir, html=True), name="static")
