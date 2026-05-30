import typer
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.align import Align
import webbrowser
import os
import time
import threading
import uvicorn
import sys

from yumi.core.global_config import update_global_config, load_global_config
from yumi.core.credential_store import (
    get_credential, save_credential, is_set, keychain_name,
)
from yumi.agent.personality_manager import personality_manager

app = typer.Typer(help="Yumi - Your AI Companion", invoke_without_command=True)
console = Console()

def clear_screen() -> None:
    """Clears the terminal screen based on the operating system."""
    os.system('cls' if os.name == 'nt' else 'clear')

def type_text(text: str, delay: float = 0.03, style: str = "bold magenta") -> None:
    """Prints text character by character for a typing effect.

    Args:
        text: The string to print.
        delay: Delay between characters in seconds.
        style: Rich style for the text.

    """
    for char in text:
        console.print(f"[{style}]{char}[/{style}]", end="")
        sys.stdout.flush()
        time.sleep(delay)
    console.print()

def mask_key(key: str | None) -> str:
    """Masks an API key for display, showing only the first and last 4 characters.

    Args:
        key: The API key string.

    """
    if not key:
        return "Not Set"
    if len(key) <= 8:
        return "********"
    return f"{key[:4]}...{key[-4:]}"

def show_story() -> None:
    """Displays Yumi's vision story and returns to the dashboard."""
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

def dashboard() -> None:
    """Renders the main Yumi status dashboard and navigation menu."""
    clear_screen()
    config = load_global_config()

    # Preferences live in config.json; secrets come from the OS keychain.
    llm_provider       = config.get("LLM_PROVIDER", "Groq")
    active_key_name    = f"{llm_provider.upper()}_API_KEY"
    llm_key            = get_credential(active_key_name)
    llm_status         = "🔐 Keychain" if llm_key else "🔴 Not set"

    tts_provider = config.get("TTS_PROVIDER", "ElevenLabs")
    if tts_provider == "CAMB.ai":
        tts_key = get_credential("CAMB_API_KEY")
        voice_id = get_credential("CAMB_VOICE_ID")
        if tts_key and voice_id:
            tts_status = "🔐 Keychain"
            voice_line = (
                f"Voice (CAMB.ai): {tts_status}  "
                f"[dim]{mask_key(tts_key)}[/dim]  "
                f"Voice ID: [dim]{voice_id[:6]}...[/dim]"
            )
        elif tts_key:
            tts_status = "🟡 Keychain"
            voice_line = (
                f"Voice (CAMB.ai): {tts_status}  [dim]{mask_key(tts_key)}[/dim]  "
                f"[yellow]Voice ID not set — go to ⚙️ Configure Senses[/yellow]"
            )
        else:
            voice_line = "Voice (CAMB.ai): 🔴  [dim]Not configured[/dim]"
    else:
        eleven_key  = get_credential("ELEVENLABS_API_KEY")
        voice_id    = get_credential("ELEVENLABS_VOICE_ID")
        if eleven_key and voice_id:
            eleven_status = "🔐 Keychain"
            voice_line = (
                f"Voice (ElevenLabs): {eleven_status}  "
                f"[dim]{mask_key(eleven_key)}[/dim]  "
                f"Voice ID: [dim]{voice_id[:6]}...[/dim]"
            )
        elif eleven_key:
            eleven_status = "🟡 Keychain"
            voice_line = (
                f"Voice (ElevenLabs): {eleven_status}  [dim]{mask_key(eleven_key)}[/dim]  "
                f"[yellow]Voice ID not set — go to ⚙️ Configure Senses[/yellow]"
            )
        else:
            voice_line = "Voice (ElevenLabs): 🔴  [dim]Not configured[/dim]"

    # STT status line
    stt_provider = config.get("STT_PROVIDER", "local")
    if stt_provider == "groq":
        groq_key     = get_credential("GROQ_API_KEY")
        stt_status   = "🔐 Keychain (Groq Whisper)" if groq_key else "🔴 Groq key missing"
    else:
        model_size   = config.get("WHISPER_MODEL_SIZE", "base")
        stt_status   = f"[dim]Local Whisper ({model_size})[/dim]"

    personality = config.get("PERSONALITY", "caring")
    kcn         = keychain_name()

    status_text = f"""
  Mind ({llm_provider}):  {llm_status}  [dim]{mask_key(llm_key or '')}[/dim]
  {voice_line}
  Ears (STT):   {stt_status}
  Personality:  [magenta]{personality}[/magenta]
  Keychain:     [dim]{kcn}[/dim]
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
def main(ctx: typer.Context) -> None:
    """Yumi - More than just code, a companion."""
    if ctx.invoked_subcommand is None:
        config          = load_global_config()
        llm_provider    = config.get("LLM_PROVIDER", "Groq")
        has_mind        = is_set(f"{llm_provider.upper()}_API_KEY")
        has_voice       = is_set("ELEVENLABS_API_KEY")

        if not has_mind and not has_voice:
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
def attune() -> None:
    """Give Yumi her senses (Onboarding & Setup)."""
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

    update_global_config("LLM_PROVIDER", llm_choice)

    key_env = f"{llm_choice.upper()}_API_KEY"
    api_key = questionary.password(f"Connect her mind ({llm_choice} API Key):", qmark="🌸").ask()
    if api_key:
        save_credential(key_env, api_key)
        console.print(f"\n[🔐] [green]Mind secured in {keychain_name()}: {mask_key(api_key)}[/green]")
        time.sleep(1)

    clear_screen()
    console.print(header)
    console.print()

    type_text("How should she sound?", style="bold cyan")
    tts_choice = questionary.select(
        "",
        choices=[
            questionary.Choice("ElevenLabs (Most expressive and lifelike)", value="ElevenLabs"),
            questionary.Choice("Kokoro (Runs locally, fast, private) - Coming Soon", value="Kokoro", disabled="Coming Soon"),
            questionary.Choice("System (Basic OS voice fallback) - Coming Soon", value="System", disabled="Coming Soon"),
        ],
        qmark="🌸"
    ).ask()

    if not tts_choice:
        raise typer.Exit()

    if tts_choice == "ElevenLabs":
        elevenlabs_key = questionary.password("Give her a voice (ElevenLabs API Key):", qmark="🌸").ask()
        if elevenlabs_key:
            save_credential("ELEVENLABS_API_KEY", elevenlabs_key)
            console.print(f"\n[🔐] [green]Voice secured in {keychain_name()}: {mask_key(elevenlabs_key)}[/green]")
            time.sleep(1)

        console.print()
        console.print("[dim]Find Voice IDs at: https://elevenlabs.io/voice-library[/dim]")
        console.print("[dim]A Voice ID looks like: 21m00Tcm4TlvDq8ikWAM[/dim]")
        voice_id = questionary.text(
            "Enter your ElevenLabs Voice ID:",
            qmark="🌸"
        ).ask()
        if voice_id and voice_id.strip():
            save_credential("ELEVENLABS_VOICE_ID", voice_id.strip())
            console.print(f"\n[🔐] [green]Voice ID secured in {keychain_name()} ✅[/green]")
            time.sleep(1)

    # STT / Listening configuration
    clear_screen()
    console.print(header)
    console.print()

    type_text("How should she listen?", style="bold cyan")
    stt_choice = questionary.select(
        "",
        choices=[
            questionary.Choice(
                "🖥  Local Whisper  (Private, works offline, no API key needed)",
                value="local"
            ),
            questionary.Choice(
                "⚡ Groq Whisper   (Cloud, ~5-10x faster, uses Groq API)",
                value="groq"
            ),
        ],
        qmark="🌸"
    ).ask()

    if stt_choice == "local":
        update_global_config("STT_PROVIDER", "local")
        model_choice = questionary.select(
            "Which Whisper model size?",
            choices=[
                questionary.Choice("tiny  — Fastest, slightly less accurate",  value="tiny"),
                questionary.Choice("base  — Recommended, balanced (default)",   value="base"),
                questionary.Choice("small — Slower, more accurate",             value="small"),
            ],
            qmark="🌸"
        ).ask()
        update_global_config("WHISPER_MODEL_SIZE", model_choice or "base")
        console.print(f"\n[green]✅ Local Whisper ({model_choice or 'base'}) configured.[/green]")
        time.sleep(1)

    elif stt_choice == "groq":
        update_global_config("STT_PROVIDER", "groq")
        existing_groq_key = get_credential("GROQ_API_KEY")
        if existing_groq_key:
            console.print(
                f"\n[green]✅ Groq API key already in {keychain_name()} — {mask_key(existing_groq_key)}[/green]"
            )
        else:
            console.print("[dim]Get a free Groq API key at: https://console.groq.com[/dim]")
            groq_key = questionary.password("Groq API Key:", qmark="🌸").ask()
            if groq_key:
                save_credential("GROQ_API_KEY", groq_key)
                console.print(f"\n[🔐] [green]Groq key secured in {keychain_name()}: {mask_key(groq_key)}[/green]")
            time.sleep(1)

    clear_screen()
    success_msg = Panel(
        Align.center("[bold green]✅ Attunement complete![/bold green]\n\nYumi is ready to wake up."),
        border_style="green"
    )
    console.print(success_msg)
    time.sleep(1.5)
    dashboard()

def change_personality() -> None:
    """Change Yumi's personality and update global preferences."""
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
def models() -> None:
    """Change the LLM and TTS providers used by Yumi."""
    clear_screen()
    config = load_global_config()

    llm_provider        = config.get("LLM_PROVIDER", "Groq")
    active_llm_key_name = f"{llm_provider.upper()}_API_KEY"
    llm_key             = get_credential(active_llm_key_name)
    kcn                 = keychain_name()

    current_state = f"""
  Mind (LLM):  [magenta]{llm_provider}[/magenta]  | 🔐 {mask_key(llm_key or '')}
  Voice (TTS): [magenta]ElevenLabs[/magenta] | 🔐 {mask_key(get_credential('ELEVENLABS_API_KEY') or '')}
  Keychain: [dim]{kcn}[/dim]
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

    if llm_choice:
        update_global_config("LLM_PROVIDER", llm_choice)
        key_env = f"{llm_choice.upper()}_API_KEY"
        api_key = questionary.password(f"New {llm_choice} API Key (leave blank to keep current):", qmark="🌸").ask()
        if api_key:
            save_credential(key_env, api_key)
            console.print(f"\n[🔐] [green]Mind secured: {mask_key(api_key)}[/green]")
            time.sleep(1)

    clear_screen()
    config              = load_global_config()
    llm_provider        = config.get("LLM_PROVIDER", "Groq")
    active_llm_key_name = f"{llm_provider.upper()}_API_KEY"
    llm_key             = get_credential(active_llm_key_name)
    tts_provider        = config.get("TTS_PROVIDER", "ElevenLabs")

    if tts_provider == "CAMB.ai":
        voice_key = get_credential("CAMB_API_KEY")
        voice_id  = get_credential("CAMB_VOICE_ID") or ""
    else:
        voice_key = get_credential("ELEVENLABS_API_KEY")
        voice_id  = get_credential("ELEVENLABS_VOICE_ID") or ""

    current_state = f"""
  Mind (LLM):  [magenta]{llm_provider}[/magenta]  | 🔐 {mask_key(llm_key or '')}
  Voice (TTS): [magenta]{tts_provider}[/magenta] | 🔐 {mask_key(voice_key or '')}
  Voice ID:    [magenta]{voice_id[:6] + '...' if voice_id else '[yellow]Not set[/yellow]'}[/magenta]
  Keychain: [dim]{kcn}[/dim]
"""
    console.print(Panel(current_state, title="[bold cyan]Current Configuration[/bold cyan]", border_style="cyan", expand=False))
    console.print()

    type_text("Switch her voice to:", style="bold cyan")
    tts_choice = questionary.select(
        "",
        choices=[
            questionary.Choice("ElevenLabs", value="ElevenLabs"),
            questionary.Choice("CAMB.ai", value="CAMB.ai"),
            questionary.Choice("Kokoro (Local) - Coming Soon", value="Kokoro", disabled="Coming Soon"),
            questionary.Choice("System - Coming Soon", value="System", disabled="Coming Soon"),
            questionary.Choice("Keep Current", value=None)
        ],
        qmark="🌸"
    ).ask()

    if tts_choice:
        update_global_config("TTS_PROVIDER", tts_choice)

    if tts_choice == "ElevenLabs":
        elevenlabs_key = questionary.password("New ElevenLabs API Key (leave blank to keep current):", qmark="🌸").ask()
        if elevenlabs_key:
            save_credential("ELEVENLABS_API_KEY", elevenlabs_key)
            console.print(f"\n[🔐] [green]Voice secured: {mask_key(elevenlabs_key)}[/green]")
            time.sleep(1)

        console.print()
        console.print(f"[dim]Current Voice ID: {voice_id if tts_provider == 'ElevenLabs' else 'Not set'}[/dim]")
        console.print("[dim]Find Voice IDs at: https://elevenlabs.io/voice-library[/dim]")
        new_voice_id = questionary.text(
            "New Voice ID (leave blank to keep current):",
            qmark="🌸"
        ).ask()
        if new_voice_id and new_voice_id.strip():
            save_credential("ELEVENLABS_VOICE_ID", new_voice_id.strip())
            console.print("\n[🔐] [green]Voice ID secured ✅[/green]")
            time.sleep(1)

    elif tts_choice == "CAMB.ai":
        camb_key = questionary.password("New CAMB.ai API Key (leave blank to keep current):", qmark="🌸").ask()
        if camb_key:
            save_credential("CAMB_API_KEY", camb_key)
            console.print(f"\n[🔐] [green]Voice secured: {mask_key(camb_key)}[/green]")
            time.sleep(1)

        console.print()
        console.print(f"[dim]Current Voice ID: {voice_id if tts_provider == 'CAMB.ai' else 'Not set'}[/dim]")
        console.print("[dim]Find Voice IDs at: https://client.camb.ai/[/dim]")
        new_voice_id = questionary.text(
            "New Voice ID (leave blank to keep current):",
            qmark="🌸"
        ).ask()
        if new_voice_id and new_voice_id.strip():
            save_credential("CAMB_VOICE_ID", new_voice_id.strip())
            console.print("\n[🔐] [green]Voice ID secured ✅[/green]")
            time.sleep(1)

    clear_screen()
    config          = load_global_config()
    stt_provider    = config.get("STT_PROVIDER", "local")
    model_size      = config.get("WHISPER_MODEL_SIZE", "base")

    stt_state = (
        f"⚡ Groq Whisper  | 🔐 {mask_key(get_credential('GROQ_API_KEY') or '')}"
        if stt_provider == "groq"
        else f"🖥  Local Whisper ({model_size})"
    )
    current_state = f"""
  Ears (STT):  [magenta]{stt_state}[/magenta]
"""
    console.print(Panel(current_state, title="[bold cyan]Listening Settings[/bold cyan]", border_style="cyan", expand=False))
    console.print()

    type_text("Switch how she listens:", style="bold cyan")
    new_stt = questionary.select(
        "",
        choices=[
            questionary.Choice("🖥  Local Whisper  (Private, offline)",        value="local"),
            questionary.Choice("⚡ Groq Whisper   (Cloud, ~5-10x faster)",    value="groq"),
            questionary.Choice("Keep Current",                                  value=None),
        ],
        qmark="🌸"
    ).ask()

    if new_stt == "local":
        update_global_config("STT_PROVIDER", "local")
        new_model = questionary.select(
            "Which Whisper model size?",
            choices=[
                questionary.Choice("tiny  — Fastest, slightly less accurate",  value="tiny"),
                questionary.Choice("base  — Recommended, balanced (default)",   value="base"),
                questionary.Choice("small — Slower, more accurate",             value="small"),
            ],
            qmark="🌸"
        ).ask()
        update_global_config("WHISPER_MODEL_SIZE", new_model or "base")
        console.print(f"\n[green]✅ Local Whisper ({new_model or 'base'}) saved.[/green]")
        time.sleep(1)

    elif new_stt == "groq":
        update_global_config("STT_PROVIDER", "groq")
        existing_groq_key = get_credential("GROQ_API_KEY")
        if existing_groq_key:
            console.print(
                f"\n[green]✅ Groq key already in {keychain_name()} — {mask_key(existing_groq_key)}[/green]"
            )
        else:
            console.print("[dim]Get a free Groq key at: https://console.groq.com[/dim]")
            groq_key = questionary.password("Groq API Key:", qmark="🌸").ask()
            if groq_key:
                save_credential("GROQ_API_KEY", groq_key)
                console.print(f"\n[🔐] [green]Groq key secured: {mask_key(groq_key)}[/green]")
            time.sleep(1)

    clear_screen()
    console.print("\n[bold green]✅ Adjustments saved![/bold green]")
    time.sleep(1)
    dashboard()

@app.command(name="wake-up")
def wake_up() -> None:
    """Wake Yumi up and start the interaction."""
    config          = load_global_config()
    llm_provider    = config.get("LLM_PROVIDER", "Groq")
    llm_key         = get_credential(f"{llm_provider.upper()}_API_KEY")

    if not llm_key:
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
    def open_browser() -> None:
        time.sleep(2)
        webbrowser.open("http://localhost:8000/")

    threading.Thread(target=open_browser, daemon=True).start()

    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

    with console.status("[bold magenta]Waking Yumi up... 🌸[/bold magenta]", spinner="point"):
        from yumi.api.server import app as fastapi_app
        time.sleep(1)

    console.print("[bold green]Yumi is awake! Opening your eyes to her...[/bold green]")
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)

@app.command()
def server() -> None:
    """Launch the Yumi API server."""
    from yumi.api.server import app as fastapi_app
    import uvicorn
    console.print("[bold magenta]Starting Yumi API server...[/bold magenta]")
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    app()
