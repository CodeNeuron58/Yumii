import os
import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List

from yumi.agent.graph import build_graph
from yumi.audio.stt import AudioPipeline
from yumi.tts.speaker import YumiSpeaker
from yumi.tts.camb_speaker import CambSpeaker
from yumi.core.config import settings

# Global connections for broadcasting
active_connections: List[WebSocket] = []
main_loop = None

# ---------------------------------------------------------------------------
# Core Engine State (The Hub)
# ---------------------------------------------------------------------------
transcription_queue = asyncio.Queue()
tts_queue = asyncio.Queue()
audio_input_queue = asyncio.Queue()
interrupt_event = asyncio.Event()

# Hardware
stt_provider = settings.stt_provider
model_size = settings.whisper_model_size
groq_api_key = settings.groq_api_key

print(f"Initializing Yumi Audio Pipeline (STT: {stt_provider})...")
pipeline = AudioPipeline(provider=stt_provider, model_size=model_size, groq_api_key=groq_api_key)

tts_provider = settings.tts_provider
print(f"Initializing Yumi Speaker (TTS: {tts_provider})...")
if tts_provider == "CAMB.ai":
    speaker = CambSpeaker()
else:
    speaker = YumiSpeaker()

# ---------------------------------------------------------------------------
# Background Tasks
# ---------------------------------------------------------------------------

async def audio_listener_task():
    """
    Task A: Continuously listens to the audio stream from the browser.
    If speech starts, it triggers the global interrupt.
    When speech ends, it transcribes and queues the text.
    """
    def on_speech_start():
        """Callback fired by STT when human speech breaks the silence threshold."""
        # 1. Fire the global interrupt flag to kill LLM and TTS tasks.
        interrupt_event.set()

        # 2. Tell the UI to instantly shut up (stop playing audio)
        payload = {"type": "interrupt"}
        if main_loop:
            asyncio.run_coroutine_threadsafe(broadcast_payload(payload), main_loop)

    print("Listener task active (streaming).")
    while True:
        try:
            # Use the new stream_capture that consumes from the WebSocket queue
            text = await pipeline.stream_capture(audio_input_queue, on_speech_start)

            if text is not None and len(text) > 0:
                # We have a captured utterance! Now we need to transcribe it.
                # Note: stream_capture returns the audio array, then we call process_audio and transcribe.
                clean_audio = pipeline.process_audio(text)
                if len(clean_audio) > 0:
                    transcribed_text = pipeline.transcribe(clean_audio)
                    if transcribed_text and transcribed_text.strip():
                        print(f"✅ Transcription: {transcribed_text}")
                        await transcription_queue.put(transcribed_text)
        except Exception as e:
            print(f"Listener crashed: {e}")
            await asyncio.sleep(1)


async def reasoning_engine_task():
    """
    Task B: Awaits text from the listener, clears interrupts, and runs LangGraph.
    """
    session_id = "yumi_session_1"
    config = {"configurable": {"thread_id": session_id}}

    print("Reasoning task active.")
    while True:
        try:
            # 1. Wait for a sentence from the STT
            user_text = await transcription_queue.get()
            
            # 2. The user has finished speaking, so we clear the interrupt flag
            interrupt_event.clear()
            
            # 3. Clear any stale sentences in the TTS queue before we think of new ones
            while not tts_queue.empty():
                try:
                    tts_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

            print(f"Reasoning starting for: {user_text}")

            # 4. Invoke LangGraph (we use ainvoke so it doesn't block)
            # Note: We are doing block-invoke here for V1 of the live flow.
            # True token streaming will be added in V2 once stability is confirmed.
            result = await graph_app.ainvoke({"input": user_text, "session_id": session_id}, config=config)

            # 5. Check if the user interrupted us while we were thinking!
            if interrupt_event.is_set():
                print("Thought interrupted before speaking! Discarding.")
                continue

            # 6. Push the result to the TTS Engine
            await tts_queue.put(result)

        except Exception as e:
            print(f"Reasoning crashed: {e}")
            await asyncio.sleep(1)


async def tts_speaker_task():
    """
    Task C: Awaits reasoning output and synthesizes audio.
    """
    print("Speaker task active.")
    while True:
        try:
            # 1. Wait for the graph to give us a YumiResponse
            result = await tts_queue.get()

            if interrupt_event.is_set():
                continue

            response_text = result["response"]
            expression = result.get("expression", "normal")
            motion = result.get("motion", "idle")

            print(f"Yumi: {response_text}")
            print(f"[{expression} | {motion}]")

            if tts_provider == "CAMB.ai":
                # CAMB.ai Streaming Implementation
                try:
                    async for chunk_data in speaker.stream_speak(response_text):
                        if interrupt_event.is_set():
                            print("TTS interrupted during stream! Discarding remaining chunks.")
                            break
                            
                        if isinstance(chunk_data, dict) and chunk_data.get("type") == "metadata":
                            # Send start metadata
                            await broadcast_payload({
                                "type": "audio_start",
                                "sampleRate": chunk_data["sampleRate"],
                                "text": response_text,
                                "expression": expression,
                                "motion": motion
                            })
                        else:
                            # Send base64 audio chunk
                            await broadcast_payload({
                                "type": "audio_chunk",
                                "data": chunk_data
                            })
                            
                    if not interrupt_event.is_set():
                        await broadcast_payload({"type": "audio_end"})
                        
                except Exception as stream_err:
                    print(f"Stream error: {stream_err}")
                    await broadcast_payload({
                        "text": response_text,
                        "expression": expression,
                        "motion": motion,
                        "audio": None,
                        "error": f"CAMB.ai TTS failed: {stream_err}"
                    })
            else:
                # ElevenLabs Blocking Implementation
                # 2. Synthesize audio (this blocks, so we run it in a thread)
                audio_b64, duration = await asyncio.to_thread(speaker.speak, response_text, False)

                if interrupt_event.is_set():
                    print("TTS interrupted during synthesis! Discarding audio.")
                    continue

                # 3. Broadcast to frontend
                if audio_b64 is None:
                    await broadcast_payload({
                        "text": response_text,
                        "expression": expression,
                        "motion": motion,
                        "audio": None,
                        "error": "TTS failed — check your ElevenLabs API key and credits."
                    })
                else:
                    await broadcast_payload({
                        "text": response_text,
                        "expression": expression,
                        "motion": motion,
                        "audio": audio_b64
                    })

                # 4. Wait for audio to finish playing, BUT allow early breakout if interrupted
                if duration > 0:
                    print(f"Waiting {duration:.2f}s for playback...")
                    # We wait in 100ms chunks so we can abort instantly if the user speaks
                    slept = 0.0
                    while slept < (duration + 0.5):
                        if interrupt_event.is_set():
                            print("Playback interrupted!")
                            break
                        await asyncio.sleep(0.1)
                        slept += 0.1

        except Exception as e:
            print(f"Speaker crashed: {e}")
            await asyncio.sleep(1)


async def broadcast_payload(payload: dict):
    """Async helper to push messages to all connected WebSockets."""
    dead_connections = []
    for connection in active_connections:
        try:
            await connection.send_text(json.dumps(payload))
        except Exception as e:
            print(f"WS Send Error: {e}")
            dead_connections.append(connection)
    for dead in dead_connections:
        active_connections.remove(dead)

# ---------------------------------------------------------------------------
# Application Setup
# ---------------------------------------------------------------------------

graph_app = build_graph()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_loop
    main_loop = asyncio.get_running_loop()
    
    # Spawn the three parallel engines
    asyncio.create_task(audio_listener_task())
    asyncio.create_task(reasoning_engine_task())
    asyncio.create_task(tts_speaker_task())
    
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
            message = await websocket.receive()
            if "text" in message:
                # Standard text message handling (if any)
                pass
            elif "bytes" in message:
                # Binary audio chunk from the browser
                await audio_input_queue.put(message["bytes"])
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)

# Mount frontend
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
webui_dir = os.path.join(package_root, "webui")
avatar_dir = os.path.join(package_root, "Yumi_Avatar")

app.mount("/Yumi_Avatar", StaticFiles(directory=avatar_dir), name="avatar")
app.mount("/", StaticFiles(directory=webui_dir, html=True), name="static")
