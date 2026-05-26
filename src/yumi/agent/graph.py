from typing import Callable
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver

from yumi.audio.stt import AudioPipeline
from yumi.tts.speaker import YumiSpeaker
from yumi.agent.nodes import chat_node
from yumi.agent.state import MainState
from yumi.core.config import settings

def build_graph(broadcast_callback: Callable):
    stt_provider   = settings.stt_provider        # "local" or "groq"
    model_size     = settings.whisper_model_size   # "tiny" / "base" / "small"
    groq_api_key   = settings.groq_api_key         # used only when provider == "groq"

    print(f"Initializing Yumi Audio Pipeline (STT: {stt_provider})...")
    pipeline = AudioPipeline(
        provider=stt_provider,
        model_size=model_size,
        groq_api_key=groq_api_key,
    )

    print("Initializing Yumi Speaker (TTS)...")
    speaker = YumiSpeaker()

    def listen_node(state: MainState):
        # This call blocks until speech is heard
        text = pipeline.run_cycle()
        return {"input": text, "expression": "normal", "motion": "idle"}
        
    def think_node(state: MainState):
        print(f"User (Audio): {state['input']}")
        # Invoke the LLM which returns {response, expression, motion, messages}
        result = chat_node({
            "input": state["input"],
            "messages": state.get("messages", []),
            "session_id": state["session_id"]
        })
        return {
            "response": result["response"],
            "expression": result["expression"] if result.get("expression") else "normal",
            "motion": result["motion"] if result.get("motion") else "idle",
            "messages": result.get("messages", [])
        }
        
    def speak_node(state: MainState):
        response_text = state["response"]
        expression = state.get("expression", "normal")
        motion = state.get("motion", "idle")

        print(f"Yumi: {response_text}")
        print(f"[{expression} | {motion}]")

        # Synthesize audio and get base64 string
        audio_b64, duration = speaker.speak(response_text, play_local=False)

        if audio_b64 is None:
            # TTS failed — broadcast the text response with an explicit error flag
            # so the frontend can show the user what went wrong instead of going mute.
            broadcast_callback({
                "text": response_text,
                "expression": expression,
                "motion": motion,
                "audio": None,
                "error": "TTS failed — check your ElevenLabs API key and credits.",
            })
        else:
            broadcast_callback({
                "text": response_text,
                "expression": expression,
                "motion": motion,
                "audio": audio_b64,
            })

        if duration > 0:
            import time
            print(f"Waiting for {duration:.2f}s while audio plays on frontend...")
            time.sleep(duration + 0.5)  # 500ms safety buffer

        print("-" * 50)
        return {"response": response_text}


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

    # Use InMemorySaver for checkpointing/conversation memory
    saver = InMemorySaver()
    return workflow.compile(checkpointer=saver)
