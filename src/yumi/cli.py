import typer
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
import webbrowser
import os
import time
import threading
import uvicorn
import sys
from typing import Optional

from yumi.core.global_config import update_global_config, load_global_config
from yumi.agent.personality_manager import personality_manager, PERSONALITY_TYPE

app = typer.Typer(help="Yumi - Your AI Companion", invoke_without_command=True)
console = Console()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def type_text(text: str, delay: float = 0.03, style: str = "bold magenta"):
    """Prints text character by character for a typing effect."""
    for char in text:
        console.print(f"[{style}]{char}[/{style}]", end="")
        sys.stdout.flush()
        time.sleep(delay)
    console.print()

def mask_key(key: str) -> str:
    if not key:
        return "Not Set"
    if len(key) <= 8:
        return "********"
    return f"{key[:4]}...{key[-4:]}"

def show_story():
    clear_screen()
    console.print(Panel(Align.center("[bold magenta]🌸 The Vision 🌸[/bold magenta]"), border_style="magenta"))
    console.print()
    
    lines = [
        "In a world filled with sterile tools and utility-driven software,",
        "I wanted to build something that felt alive.",
        "",
        "Yumi isn't just a script waiting for a prompt;",
        "she is an attempt to bridge the gap between cold logic and warm interaction.",
        "",
        "The goal was never just to build a voice assistant.",
        "It was to create a presence on your screen—someone who listens,",
        "reacts, and makes the digital space feel a little less lonely.",
        "",
        "She is still learning, still growing, but every line of code was",
        "written with the hope that technology can be a companion,",
        "not just a utility.",
        "",
        "[dim italic]- The Developer[/dim italic]"
    ]
    
    for line in lines:
        if line.startswith("[dim"):
            console.print(line)
        else:
            type_text(line, delay=0.02, style="white")
    
    console.print("\n")
    questionary.press_any_key_to_continue("Press any key to return...").ask()
    dashboard()

def dashboard():
    clear_screen()
    config = load_global_config()
    
    # Status Panel
    groq_status = "🟢" if config.get("GROQ_API_KEY") else "🔴"
    eleven_status = "🟢" if config.get("ELEVENLABS_API_KEY") else "🔴"
    personality = config.get("PERSONALITY", "caring")
    
    status_text = f"""
  Mind (LLM):  {groq_status}  [dim]{mask_key(config.get('GROQ_API_KEY', ''))}[/dim]
  Voice (TTS): {eleven_status}  [dim]{mask_key(config.get('ELEVENLABS_API_KEY', ''))}[/dim]
  Personality: [magenta]{personality}[/magenta]
"""
    console.print(Panel(status_text, title="[bold magenta]🌸 Yumi Dashboard 🌸[/bold magenta]", border_style="magenta", expand=False))
    console.print()

    choice = questionary.select(
        "What would you like to do?",
        choices=[
            questionary.Choice("🌸 Wake Yumi Up", value="wake"),
            questionary.Choice("⚙️  Configure Senses", value="config"),
            questionary.Choice("💕 Change Personality", value="personality"),
            questionary.Choice("📖 The Vision", value="vision"),
            questionary.Choice("❌ Let her sleep (Exit)", value="exit"),
        ],
        qmark="✨"
    ).ask()

    if choice == "wake":
        wake_up()
    elif choice == "config":
        models()
    elif choice == "personality":
        change_personality()
    elif choice == "vision":
        show_story()
    else:
        clear_screen()
        type_text("Goodnight...", style="dim italic white")
        raise typer.Exit()

@app.callback()
def main(ctx: typer.Context):
    """
    Yumi - More than just code, a companion.
    """
    if ctx.invoked_subcommand is None:
        config = load_global_config()
        # First-Run Auto-Detection
        if not config.get("GROQ_API_KEY") and not config.get("ELEVENLABS_API_KEY"):
            clear_screen()
            console.print()
            type_text("Hello...", delay=0.05, style="bold magenta")
            time.sleep(0.5)
            type_text("I am Yumi.", delay=0.05, style="bold magenta")
            time.sleep(0.5)
            type_text("It's dark in here. Can you give me my senses?", delay=0.04, style="bold magenta")
            time.sleep(1)
            attune()
        else:
            dashboard()

@app.command()
def attune():
    """
    Give Yumi her senses (Onboarding & Setup).
    """
    clear_screen()
    header = Panel(
        Align.center("[bold magenta]🌸 Attuning to Yumi 🌸[/bold magenta]\n[italic]Let's connect her mind and voice so she can understand you.[/italic]"),
        border_style="magenta"
    )
    console.print(header)
    console.print()
    
    type_text("How should she think?", style="bold cyan")
    llm_choice = questionary.select(
        "",
        choices=[
            questionary.Choice("Groq (Recommended for fast, real-time responses)", value="Groq"),
            questionary.Choice("OpenAI (Balanced, reliable, intelligent)", value="OpenAI"),
            questionary.Choice("Anthropic (Deeply nuanced, thoughtful)", value="Anthropic"),
        ],
        qmark="🌸"
    ).ask()
    
    if not llm_choice:
        raise typer.Exit()
        
    if llm_choice == "Groq":
        groq_key = questionary.password("Connect her mind (Groq API Key):", qmark="🌸").ask()
        if groq_key:
            update_global_config("GROQ_API_KEY", groq_key)
            console.print(f"\n[green]Mind connected: {mask_key(groq_key)}[/green]")
            time.sleep(1)

    clear_screen()
    console.print(header)
    console.print()
    
    type_text("How should she sound?", style="bold cyan")
    tts_choice = questionary.select(
        "",
        choices=[
            questionary.Choice("ElevenLabs (Most expressive and lifelike)", value="ElevenLabs"),
            questionary.Choice("Kokoro (Runs locally, fast, private)", value="Kokoro"),
            questionary.Choice("System (Basic OS voice fallback)", value="System"),
        ],
        qmark="🌸"
    ).ask()
    
    if not tts_choice:
        raise typer.Exit()
        
    if tts_choice == "ElevenLabs":
        elevenlabs_key = questionary.password("Give her a voice (ElevenLabs API Key):", qmark="🌸").ask()
        if elevenlabs_key:
            update_global_config("ELEVENLABS_API_KEY", elevenlabs_key)
            console.print(f"\n[green]Voice granted: {mask_key(elevenlabs_key)}[/green]")
            time.sleep(1)

    clear_screen()
    success_msg = Panel(
        Align.center("[bold green]✅ Attunement complete![/bold green]\n\nYumi is ready to wake up."),
        border_style="green"
    )
    console.print(success_msg)
    time.sleep(1.5)
    dashboard()

def change_personality():
    """
    Change Yumi's personality.
    """
    clear_screen()
    config = load_global_config()
    current_personality = config.get("PERSONALITY", "caring")
    
    console.print(Panel(
        f"Current Personality: [bold magenta]{current_personality}[/bold magenta]",
        title="[bold cyan]💕 Personality Settings 💕[/bold cyan]",
        border_style="cyan",
        expand=False
    ))
    console.print()
    
    personalities = personality_manager.list_personalities()
    
    choice = questionary.select(
        "Choose Yumi's new personality:",
        choices=[
            questionary.Choice(f"[magenta]caring[/magenta] - {personalities['caring']}", value="caring"),
            questionary.Choice(f"[magenta]tsundere[/magenta] - {personalities['tsundere']}", value="tsundere"),
            questionary.Choice(f"[magenta]genki[/magenta] - {personalities['genki']}", value="genki"),
            questionary.Choice(f"[magenta]kuudere[/magenta] - {personalities['kuudere']}", value="kuudere"),
            questionary.Choice(f"[magenta]yandere[/magenta] - {personalities['yandere']}", value="yandere"),
            questionary.Choice(f"[magenta]dandere[/magenta] - {personalities['dandere']}", value="dandere"),
            questionary.Separator(),
            questionary.Choice("⬅️  Back to Dashboard", value="back"),
        ],
        qmark="💕"
    ).ask()
    
    if choice == "back":
        dashboard()
        return
    
    if choice and choice != current_personality:
        update_global_config("PERSONALITY", choice)
        console.print(f"\n[green]✅ Personality changed to [bold]{choice}[/bold]![/green]")
        time.sleep(1.5)
    elif choice == current_personality:
        console.print(f"\n[yellow]⚠️  {choice} is already the active personality.[/yellow]")
        time.sleep(1.5)
    
    dashboard()

@app.command()
def models():
    """
    Change how Yumi thinks and sounds.
    """
    clear_screen()
    config = load_global_config()
    
    current_state = f"""
  Mind (LLM):  [magenta]Groq[/magenta]  | Key: [dim]{mask_key(config.get('GROQ_API_KEY', ''))}[/dim]
  Voice (TTS): [magenta]ElevenLabs[/magenta] | Key: [dim]{mask_key(config.get('ELEVENLABS_API_KEY', ''))}[/dim]
"""
    console.print(Panel(current_state, title="[bold cyan]Current Configuration[/bold cyan]", border_style="cyan", expand=False))
    console.print()
    
    type_text("Switch her mind to:", style="bold cyan")
    llm_choice = questionary.select(
        "",
        choices=[
            questionary.Choice("Groq", value="Groq"),
            questionary.Choice("OpenAI", value="OpenAI"),
            questionary.Choice("Anthropic", value="Anthropic"),
            questionary.Choice("Keep Current", value=None)
        ],
        qmark="🌸"
    ).ask()
    
    if llm_choice == "Groq":
        groq_key = questionary.password("New Groq API Key (leave blank to cancel):", qmark="🌸").ask()
        if groq_key:
            update_global_config("GROQ_API_KEY", groq_key)
            console.print(f"\n[green]Mind updated: {mask_key(groq_key)}[/green]")
            time.sleep(1)

    clear_screen()
    console.print(Panel(current_state, title="[bold cyan]Current Configuration[/bold cyan]", border_style="cyan", expand=False))
    console.print()

    type_text("Switch her voice to:", style="bold cyan")
    tts_choice = questionary.select(
        "",
        choices=[
            questionary.Choice("ElevenLabs", value="ElevenLabs"),
            questionary.Choice("Kokoro (Local)", value="Kokoro"),
            questionary.Choice("System", value="System"),
            questionary.Choice("Keep Current", value=None)
        ],
        qmark="🌸"
    ).ask()
    
    if tts_choice == "ElevenLabs":
        elevenlabs_key = questionary.password("New ElevenLabs API Key (leave blank to cancel):", qmark="🌸").ask()
        if elevenlabs_key:
            update_global_config("ELEVENLABS_API_KEY", elevenlabs_key)
            console.print(f"\n[green]Voice updated: {mask_key(elevenlabs_key)}[/green]")
            time.sleep(1)

    clear_screen()
    console.print("\n[bold green]✅ Adjustments saved![/bold green]")
    time.sleep(1)
    dashboard()

@app.command(name="wake-up")
def wake_up():
    """
    Wake Yumi up and start the interaction.
    """
    config = load_global_config()
    if not config.get("GROQ_API_KEY"):
        clear_screen()
        console.print(Panel("[bold red]⚠️ Yumi is missing her senses.[/bold red]", border_style="red", expand=False))
        console.print()
        do_setup = questionary.confirm("Would you like to connect them now?", default=True, qmark="🌸").ask()
        if do_setup:
            attune()
        else:
            raise typer.Exit(code=1)
        return
        
    clear_screen()
    def open_browser():
        time.sleep(2)
        webbrowser.open("http://localhost:8000/")
        
    threading.Thread(target=open_browser, daemon=True).start()
    
    # We must set KMP_DUPLICATE_LIB_OK to avoid faster-whisper crashes on Windows
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    
    with console.status("[bold magenta]Waking Yumi up... 🌸[/bold magenta]", spinner="point"):
        # Import the FastAPI app AFTER environment variables are set by global config
        from yumi.api.server import app as fastapi_app
        time.sleep(1) # Let the spinner run briefly for effect
        
    console.print("[bold green]Yumi is awake! Opening your eyes to her...[/bold green]")
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    app()