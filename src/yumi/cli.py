import typer
from rich.console import Console
from rich.prompt import Prompt
import webbrowser
import os
import time
import threading
import uvicorn

from yumi.core.global_config import update_global_config, load_global_config

app = typer.Typer(help="Yumi CLI - Your AI Companion", no_args_is_help=True)
console = Console()

@app.command()
def onboard():
    """
    Run the interactive onboarding process to set up API keys.
    """
    console.print("\n[bold magenta]🌸 Welcome to Yumi Setup! 🌸[/bold magenta]")
    console.print("Let's get you set up so you can start chatting.\n")
    
    llm_provider = Prompt.ask(
        "Select your LLM provider", 
        choices=["Groq", "OpenAI", "Anthropic"], 
        default="Groq"
    )
    
    if llm_provider == "Groq":
        groq_key = Prompt.ask("Enter your Groq API Key")
        if groq_key:
            update_global_config("GROQ_API_KEY", groq_key)
            
    tts_provider = Prompt.ask(
        "Select your TTS provider", 
        choices=["ElevenLabs", "Kokoro (Local)", "System"], 
        default="ElevenLabs"
    )
    
    if tts_provider == "ElevenLabs":
        elevenlabs_key = Prompt.ask("Enter your ElevenLabs API Key")
        if elevenlabs_key:
            update_global_config("ELEVENLABS_API_KEY", elevenlabs_key)
            
    console.print("\n[bold green]✅ Setup complete![/bold green]")
    console.print("You can now run [bold cyan]yumi start[/bold cyan] to launch the app.\n")


@app.command()
def start():
    """
    Start the Yumi server and open the web UI in your browser.
    """
    console.print("[bold green]Starting Yumi...[/bold green]")
    
    config = load_global_config()
    if not config.get("GROQ_API_KEY"):
        console.print("[bold red]⚠️  Configuration missing. Please run 'yumi onboard' first.[/bold red]")
        raise typer.Exit(code=1)
        
    def open_browser():
        time.sleep(2)
        console.print("[bold cyan]Opening browser...[/bold cyan]")
        webbrowser.open("http://localhost:8000/webui/index.html")
        
    threading.Thread(target=open_browser, daemon=True).start()
    
    # We must set KMP_DUPLICATE_LIB_OK to avoid faster-whisper crashes on Windows
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    
    # Import the FastAPI app AFTER environment variables are set by global config
    from yumi.api.server import app as fastapi_app
    
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    app()
