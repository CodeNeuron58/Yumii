import os
import asyncio
import json
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import TypedDict, List, Annotated
import operator
from langgraph.graph import StateGraph, END

from Yumi_Hears.pipeline import AudioPipeline
from Yumi_Speaks.tts import YumiSpeaker
from Yumi_Brain.nodes import chat_node

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global clients to broadcast to UI
active_connections: List[WebSocket] = []

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


class MainState(TypedDict):
    input: Annotated[str, operator.add]
    response: Annotated[str, operator.add]
    expression: Annotated[str, lambda x, y: y if y is not None else x]
    motion: Annotated[str, lambda x, y: y if y is not None else x]
    session_id: str


print("Initializing Yumi Audio Pipeline...")
pipeline = AudioPipeline()

print("Initializing Yumi Speaker (TTS)...")
speaker = YumiSpeaker()

session_id = "yumi_session_1"

# --- Define Graph Nodes ---
def listen_node(state: MainState):
    # This call blocks until speech is heard
    text = pipeline.run_cycle()
    return {"input": text, "expression": "normal", "motion": "idle"}
    
def think_node(state: MainState):
    print(f"User (Audio): {state['input']}")
    # Invoke the LLM which returns {response, expression, motion}
    result = chat_node({
        "input": state["input"],
        "session_id": state["session_id"]
    })
    # --- EMOTION/MOTION HANDLING (Step 2) ---
    # The LLM output logic parses those fields. If they are missing or invalid,
    # we provide safe fallbacks ("normal" for expression, "idle" for motion).
    return {
        "response": result["response"],
        "expression": result["expression"] if result.get("expression") else "normal",
        "motion": result["motion"] if result.get("motion") else "idle"
    }
    
def speak_node(state: MainState):
    response_text = state["response"]
    expression = state.get("expression", "LOST")
    motion = state.get("motion", "LOST")
    
    print(f"\nDEBUG: Flow to speak node! raw expr={expression}, raw mot={motion}\n")
    
    print(f"Yumi: {response_text}")
    print(f"[{expression} | {motion}]")
    
    # Synthesize audio and get base64 string
    audio_b64, duration = speaker.speak(response_text, play_local=False)
    
    # --- EMOTION/MOTION HANDLING (Step 3) ---
    # The expression and motion fields (now populated by the LLM) are bundled into the JSON payload.
    # This payload is sent via WebSocket to the frontend web UI to trigger the Live2D animations.
    payload = {
        "text": response_text,
        "expression": expression,
        "motion": motion,
        "audio": audio_b64
    }
    
    # Broadcast to all connected web UIs
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
            
    # Run the broadcast synchronously since `speak_node` is already in `asyncio.to_thread`
    try:
        asyncio.run(broadcast())
    except Exception as e:
        print(f"Failed to broadcast WS: {e}")
    
    if duration > 0:
        import time
        print(f"Waiting for {duration:.2f} seconds while audio plays on frontend before listening again...")
        time.sleep(duration + 0.5)  # add 500ms safety buffer
        
    print("-" * 50)
    return {"response": response_text}
    
# --- Define Routing ---
def should_think(state: MainState):
    if state.get("input") and state["input"].strip():
        return "think"
    return "end"

print("Building LangGraph...")
workflow = StateGraph(MainState)

workflow.add_node("listen", listen_node)
workflow.add_node("think", think_node)
workflow.add_node("speak", speak_node)

workflow.set_entry_point("listen")

workflow.add_conditional_edges(
    "listen",
    should_think,
    {
        "think": "think",
        "end": END
    }
)
workflow.add_edge("think", "speak")
workflow.add_edge("speak", END)

graph_app = workflow.compile()


# --- Background Agent Loop ---
async def agent_loop():
    print("Agent loop started. Waiting 2 seconds for server to boot...")
    await asyncio.sleep(2)
    print("System ready. Listening for speech...")
    
    while True:
        try:
            # We run the synchronous graph invocation in a threadpool so it doesn't block the FastAPI async event loop
            await asyncio.to_thread(
                graph_app.invoke,
                {
                    "input": "", 
                    "response": "", 
                    "expression": "",
                    "motion": "",
                    "session_id": session_id
                }
            )
        except Exception as e:
            print(f"Agent Loop Error: {e}")
            await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(agent_loop())

# Mount the static files (this must be declared after all API/WS routes)
app.mount("/", StaticFiles(directory=os.path.dirname(os.path.abspath(__file__)), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)