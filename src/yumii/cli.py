# -*- coding: utf-8 -*-
"""Command Line Interface (CLI) for Yumii.

Premium terminal experience — pixel-art banner, REPL shell, and
styled dialogs powered by Rich + prompt_toolkit.
"""

from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser


import typer
import uvicorn
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.shortcuts import (
    input_dialog,
    message_dialog,
    radiolist_dialog,
    yes_no_dialog,
)
from prompt_toolkit.styles import Style
from rich import box
from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from yumii.agent.personality_manager import personality_manager
from yumii.core.credential_store import (
    get_credential,
    is_set,
    save_credential,
)
from yumii.core.global_config import load_global_config, update_global_config

from yumii.core.logging import configure_logging, get_logger
configure_logging()
log = get_logger(__name__)

# ─── Package Version ──────────────────────────────────────────────────────────
try:
    from importlib.metadata import version as _pkg_version

    VERSION = _pkg_version("yumii")
except Exception:
    VERSION = "0.1.0"

# ─── Typer App & Rich Console ─────────────────────────────────────────────────
app = typer.Typer(help="Yumii — Your AI Companion", invoke_without_command=True)
console = Console()

# ─── Yumii Color Palette ───────────────────────────────────────────────────────
_C_PRIMARY  = "#00d4aa"   # teal-green    (main accent)
_C_NEON     = "#00ff88"   # neon green    (banner left edge)
_C_CYAN     = "#00b8d4"   # cyan          (banner right edge)
_C_TEXT     = "#c9d1d9"   # near-white    (body text)
_C_DIM      = "#6e7681"   # muted gray    (tips, hints, toolbar)
_C_BG       = "#0d1117"   # near-black    (dialog background)
_C_PANEL    = "#161b22"   # dark panel    (toolbar background)
_C_SUCCESS  = "#3fb950"   # bright green  (success messages)
_C_WARNING  = "#d29922"   # amber         (warnings)
_C_ERROR    = "#f85149"   # coral red     (errors)

# ─── prompt_toolkit Styles ────────────────────────────────────────────────────
_DIALOG_STYLE = Style.from_dict({
    # Dialog chrome
    "dialog":                 f"bg:{_C_BG}",
    "dialog shadow":          "bg:#000000",
    "dialog frame":           f"bg:{_C_BG} fg:{_C_PRIMARY}",
    "dialog frame.label":     f"bg:{_C_PRIMARY} fg:{_C_BG} bold",
    "dialog.body":            f"bg:{_C_BG} fg:{_C_TEXT}",
    "dialog.body label":      f"fg:{_C_TEXT}",
    # Buttons
    "button":                 f"bg:{_C_PANEL} fg:{_C_DIM}",
    "button.focused":         f"bg:{_C_PRIMARY} fg:{_C_BG} bold",
    "button.arrow":           f"fg:{_C_PRIMARY} bold",
    # Text input
    "text-area":              f"bg:{_C_PANEL} fg:{_C_TEXT}",
    "text-area.prompt":       f"fg:{_C_PRIMARY}",
    # Radio / checkbox lists
    "radio-list":             f"bg:{_C_BG} fg:{_C_TEXT}",
    "checkbox-list":          f"bg:{_C_BG} fg:{_C_TEXT}",
    "radio-list radio":       f"fg:{_C_PRIMARY}",
    "checkbox-list checkbox": f"fg:{_C_PRIMARY}",
    # Scrollbar
    "scrollbar.background":   f"bg:{_C_PANEL}",
    "scrollbar.button":       f"bg:{_C_PRIMARY}",
    # Bottom toolbar
    "bottom-toolbar":         f"bg:{_C_PANEL} fg:{_C_DIM}",
    "bottom-toolbar.text":    f"bg:{_C_PANEL} fg:{_C_DIM}",
})

_REPL_STYLE = Style.from_dict({
    "prompt":              f"fg:{_C_PRIMARY} bold",
    "bottom-toolbar":      f"bg:{_C_PANEL} fg:{_C_DIM}",
    "bottom-toolbar.text": f"bg:{_C_PANEL} fg:{_C_DIM}",
})

# ─── Pixel-Art Banner ─────────────────────────────────────────────────────────
_BANNER = [
    "██╗   ██╗██╗   ██╗███╗   ███╗██╗ ██╗",
    "╚██╗ ██╔╝██║   ██║████╗ ████║██║ ██║",
    " ╚████╔╝ ██║   ██║██╔████╔██║██║ ██║",
    "  ╚██╔╝  ██║   ██║██║╚██╔╝██║██║ ██║",
    "   ██║   ╚██████╔╝██║ ╚═╝ ██║██║ ██║",
    "   ╚═╝    ╚═════╝ ╚═╝     ╚═╝╚═╝ ╚═╝",
]
_GRAD_L = (0, 255, 136)   # #00ff88
_GRAD_R = (0, 184, 212)   # #00b8d4


def _lerp_hex(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> str:
    r  = int(a[0] + t * (b[0] - a[0]))
    g  = int(a[1] + t * (b[1] - a[1]))
    bl = int(a[2] + t * (b[2] - a[2]))
    return f"#{r:02x}{g:02x}{bl:02x}"


def render_banner() -> None:
    """Render the YUMII pixel-art banner with a green → cyan gradient."""
    width = max(len(row) for row in _BANNER)
    console.print()
    for row in _BANNER:
        text = Text()
        for i, ch in enumerate(row):
            t = i / max(width - 1, 1)
            text.append(ch, style=f"bold {_lerp_hex(_GRAD_L, _GRAD_R, t)}")
        console.print(Align.center(text))
    console.print()
    console.print(
        Align.center(Text(f"Your AI Companion  ·  v{VERSION}", style=f"dim {_C_DIM}"))
    )
    console.print()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def clear_screen() -> None:
    """Clear the terminal."""
    os.system("cls" if os.name == "nt" else "clear")


def mask_key(key: str | None) -> str:
    """Mask an API key for safe display."""
    if not key:
        return "Not Set"
    if len(key) <= 8:
        return "●●●●●●●●"
    return f"{key[:4]}···{key[-4:]}"


def type_text(text: str, delay: float = 0.03, style: str | None = None) -> None:
    """Print text character-by-character for a typewriter effect."""
    if style is None:
        style = f"bold {_C_PRIMARY}"
    for char in text:
        console.print(f"[{style}]{char}[/{style}]", end="")
        sys.stdout.flush()
        time.sleep(delay)
    console.print()


# ─── Tips Section ─────────────────────────────────────────────────────────────

def render_tips() -> None:
    """Render the getting-started tips below the banner."""
    console.print(f"  [{_C_DIM}]Tips for getting started:[/]")
    tips: list[tuple[str, str]] = [
        ("Just talk",     " — ask anything, give commands, or just chat."),
        ("/wake",         " to bring Yumii to life with her full avatar."),
        ("/config",       " to adjust her mind, voice, and listening."),
        ("/help",         " to see all available commands."),
    ]
    for i, (key, rest) in enumerate(tips, 1):
        line = Text()
        line.append(f"  {i}. ", style=_C_DIM)
        if key.startswith("/"):
            line.append(key, style=f"bold {_C_PRIMARY}")
        else:
            line.append(key, style=_C_TEXT)
        line.append(rest, style=_C_DIM)
        console.print(line)
    console.print()


# ─── Bottom Toolbar ───────────────────────────────────────────────────────────

def _toolbar() -> HTML:
    """Dynamic bottom toolbar showing live config state."""
    try:
        config      = load_global_config()
        provider    = config.get("LLM_PROVIDER", "Groq")
        personality = config.get("PERSONALITY", "caring")
    except Exception:
        provider, personality = "Groq", "caring"

    cwd = os.path.basename(os.path.abspath(os.getcwd())) or "~"
    return HTML(
        f' <style bg="{_C_PANEL}" fg="{_C_DIM}">~/{cwd}</style>'
        f'<style bg="{_C_PANEL}" fg="{_C_DIM}">    </style>'
        f'<style bg="{_C_PANEL}" fg="{_C_PRIMARY}">{provider}</style>'
        f'<style bg="{_C_PANEL}" fg="{_C_DIM}"> · </style>'
        f'<style bg="{_C_PANEL}" fg="{_C_PRIMARY}">{personality}</style>'
        f'<style bg="{_C_PANEL}" fg="{_C_DIM}">    Yumii {VERSION} </style>'
    )


# ─── Help Screen ──────────────────────────────────────────────────────────────

# ── Command registry — add new entries here and help auto-updates ─────────────
_COMMANDS: list[tuple[str, str, str]] = [
    # (command,         aliases hint,            description)
    ("/wake",         "",                       "Wake Yumii up — launch her avatar server and open the browser"),
    ("/config",       "configure · settings",   "Configure mind (LLM), voice (TTS), and ears (STT)"),
    ("/personality",  "",                       "Switch Yumii's personality mode"),
    ("/vision",       "story",                  "Read the story and roadmap behind Yumii"),
    ("/help",         "h · ?",                  "Show this help screen"),
    ("/exit",         "quit · q",               "Let Yumii sleep — exit gracefully"),
]


def _show_help() -> None:
    """Render the help table inline (terminal scrolls naturally)."""
    table = Table(
        show_header=True,
        header_style=f"bold {_C_PRIMARY}",
        border_style=_C_PANEL,
        box=box.SIMPLE_HEAVY,
        padding=(0, 2),
        show_lines=False,
        min_width=70,
    )
    table.add_column("Command",     style=f"{_C_PRIMARY} bold", min_width=16, no_wrap=True)
    table.add_column("Aliases",     style=_C_DIM,               min_width=18, no_wrap=True)
    table.add_column("Description", style=_C_TEXT)

    for cmd, aliases, desc in _COMMANDS:
        table.add_row(cmd, aliases or "-", desc)

    console.print()
    console.print(Align.center(Text("Yumii Commands", style=f"bold {_C_PRIMARY}")))
    console.print(Align.center(Text("-" * 70, style=_C_PANEL)))
    console.print()
    console.print(
        Panel(
            table,
            border_style=_C_PRIMARY,
            expand=False,
            padding=(1, 2),
        )
    )
    console.print(f"  [{_C_DIM}]Tip: commands work with or without the leading /[/]")
    console.print()


def _goodbye() -> None:
    """Print the exit farewell message."""
    console.print()
    type_text("Goodnight... 🌿", delay=0.05, style=f"dim italic {_C_DIM}")
    console.print()


# ─── Wizard: Attune (First-Run Setup) ─────────────────────────────────────────

def run_attune_wizard() -> bool:
    """Walk the user through first-run setup. Returns True on success."""

    # ── Step 1 · LLM Provider ─────────────────────────────────────────────────
    llm_choice = radiolist_dialog(
        title="🌿  Yumii's Mind — How should she think?",
        text="Choose a language model provider:\n",
        values=[
            ("Groq",      "Groq         Fast, real-time responses  (recommended)"),
            ("OpenAI",    "OpenAI       Balanced and reliable"),
            ("Anthropic", "Anthropic    Deeply thoughtful and nuanced"),
        ],
        ok_text="Next  ❯",
        cancel_text="Cancel",
        style=_DIALOG_STYLE,
    ).run()

    if llm_choice is None:
        return False
    update_global_config("LLM_PROVIDER", llm_choice)

    api_key = input_dialog(
        title=f"🌿  {llm_choice} API Key",
        text=f"Enter your {llm_choice} API key:",
        password=True,
        ok_text="Save",
        cancel_text="Skip",
        style=_DIALOG_STYLE,
    ).run()
    if api_key:
        save_credential(f"{llm_choice.upper()}_API_KEY", api_key)

    # ── Step 2 · TTS Provider ─────────────────────────────────────────────────
    tts_choice = radiolist_dialog(
        title="🌿  Yumii's Voice — How should she sound?",
        text="Choose a text-to-speech provider:\n",
        values=[
            ("ElevenLabs", "ElevenLabs   Most expressive and lifelike  (recommended)"),
            ("CAMB.ai",    "CAMB.ai      High-quality alternative"),
        ],
        ok_text="Next  ❯",
        cancel_text="Back",
        style=_DIALOG_STYLE,
    ).run()

    if tts_choice is None:
        return False
    update_global_config("TTS_PROVIDER", tts_choice)

    if tts_choice == "ElevenLabs":
        el_key = input_dialog(
            title="🌿  ElevenLabs API Key",
            text=(
                "Enter your ElevenLabs API key:\n"
                "(elevenlabs.io → Profile → API Keys)"
            ),
            password=True,
            ok_text="Save",
            cancel_text="Skip",
            style=_DIALOG_STYLE,
        ).run()
        if el_key:
            save_credential("ELEVENLABS_API_KEY", el_key)

        voice_id = input_dialog(
            title="🌿  ElevenLabs Voice ID",
            text=(
                "Enter your ElevenLabs Voice ID:\n"
                "(Browse: elevenlabs.io/voice-library)\n"
                " Example: 21m00Tcm4TlvDq8ikWAM"
            ),
            ok_text="Save",
            cancel_text="Skip",
            style=_DIALOG_STYLE,
        ).run()
        if voice_id and voice_id.strip():
            save_credential("ELEVENLABS_VOICE_ID", voice_id.strip())

    elif tts_choice == "CAMB.ai":
        camb_key = input_dialog(
            title="🌿  CAMB.ai API Key",
            text="Enter your CAMB.ai API key:\n(client.camb.ai)",
            password=True,
            ok_text="Save",
            cancel_text="Skip",
            style=_DIALOG_STYLE,
        ).run()
        if camb_key:
            save_credential("CAMB_API_KEY", camb_key)

        voice_id = input_dialog(
            title="🌿  CAMB.ai Voice ID",
            text="Enter your CAMB.ai Voice ID:",
            ok_text="Save",
            cancel_text="Skip",
            style=_DIALOG_STYLE,
        ).run()
        if voice_id and voice_id.strip():
            save_credential("CAMB_VOICE_ID", voice_id.strip())

    # ── Step 3 · STT Provider ─────────────────────────────────────────────────
    stt_choice = radiolist_dialog(
        title="🌿  Yumii's Ears — How should she listen?",
        text="Choose a speech-to-text provider:\n",
        values=[
            ("local", "Local Whisper   Private, works offline, no API key needed"),
            ("groq",  "Groq Whisper    Cloud-based, ~5-10× faster (uses Groq API)"),
        ],
        ok_text="Next  ❯",
        cancel_text="Skip",
        style=_DIALOG_STYLE,
    ).run()

    if stt_choice == "local":
        update_global_config("STT_PROVIDER", "local")
        model = radiolist_dialog(
            title="🌿  Whisper Model Size",
            text="Choose the local Whisper model size:\n(Larger = more accurate, slower to load)\n",
            values=[
                ("tiny",  "tiny    Fastest, slightly less accurate"),
                ("base",  "base    Recommended — balanced  (default)"),
                ("small", "small   Slower, more accurate"),
            ],
            ok_text="Save",
            cancel_text="Use Default",
            style=_DIALOG_STYLE,
        ).run()
        update_global_config("WHISPER_MODEL_SIZE", model or "base")

    elif stt_choice == "groq":
        update_global_config("STT_PROVIDER", "groq")
        existing = get_credential("GROQ_API_KEY")
        if not existing:
            groq_key = input_dialog(
                title="🌿  Groq API Key",
                text="Enter your Groq API key:\n(Free at: console.groq.com)",
                password=True,
                ok_text="Save",
                cancel_text="Skip",
                style=_DIALOG_STYLE,
            ).run()
            if groq_key:
                save_credential("GROQ_API_KEY", groq_key)

    # ── Done ──────────────────────────────────────────────────────────────────
    message_dialog(
        title="🌿  Setup Complete",
        text=(
            "Yumii's senses are connected!\n\n"
            "She is ready to wake up.\n"
            "Type  /wake  in the shell to bring her to life."
        ),
        ok_text="Let's Go  ❯",
        style=_DIALOG_STYLE,
    ).run()

    return True


# ─── Wizard: Configure (Models / Providers) ───────────────────────────────────

def run_models_wizard() -> None:
    """Full configuration wizard for LLM, TTS, and STT providers."""
    config = load_global_config()

    # ── LLM ───────────────────────────────────────────────────────────────────
    current_llm = config.get("LLM_PROVIDER", "Groq")
    llm_choice = radiolist_dialog(
        title="⚙️   Configure Mind (LLM)",
        text=f"Currently using: {current_llm}\n\nSwitch to:\n",
        values=[
            ("Groq",      f"Groq         Fast, real-time{' ✓' if current_llm == 'Groq' else ''}"),
            ("OpenAI",    f"OpenAI       Balanced, reliable{' ✓' if current_llm == 'OpenAI' else ''}"),
            ("Anthropic", f"Anthropic    Deeply thoughtful{' ✓' if current_llm == 'Anthropic' else ''}"),
            (None,        "Keep current"),
        ],
        ok_text="Next  ❯",
        cancel_text="Skip",
        style=_DIALOG_STYLE,
    ).run()

    if llm_choice:
        update_global_config("LLM_PROVIDER", llm_choice)
        api_key = input_dialog(
            title=f"⚙️   {llm_choice} API Key",
            text=f"New {llm_choice} API key (blank = keep current):",
            password=True,
            ok_text="Save",
            cancel_text="Skip",
            style=_DIALOG_STYLE,
        ).run()
        if api_key:
            save_credential(f"{llm_choice.upper()}_API_KEY", api_key)

    # ── TTS ───────────────────────────────────────────────────────────────────
    config      = load_global_config()
    current_tts = config.get("TTS_PROVIDER", "ElevenLabs")
    tts_choice  = radiolist_dialog(
        title="⚙️   Configure Voice (TTS)",
        text=f"Currently using: {current_tts}\n\nSwitch to:\n",
        values=[
            ("ElevenLabs", f"ElevenLabs   Most expressive{' ✓' if current_tts == 'ElevenLabs' else ''}"),
            ("CAMB.ai",    f"CAMB.ai      High-quality alternative{' ✓' if current_tts == 'CAMB.ai' else ''}"),
            (None,         "Keep current"),
        ],
        ok_text="Next  ❯",
        cancel_text="Skip",
        style=_DIALOG_STYLE,
    ).run()

    if tts_choice:
        update_global_config("TTS_PROVIDER", tts_choice)
        if tts_choice == "ElevenLabs":
            key = input_dialog(
                title="⚙️   ElevenLabs API Key",
                text="New API key (blank = keep current):",
                password=True,
                ok_text="Save",
                cancel_text="Skip",
                style=_DIALOG_STYLE,
            ).run()
            if key:
                save_credential("ELEVENLABS_API_KEY", key)

            vid = input_dialog(
                title="⚙️   ElevenLabs Voice ID",
                text="New Voice ID (blank = keep current):",
                ok_text="Save",
                cancel_text="Skip",
                style=_DIALOG_STYLE,
            ).run()
            if vid and vid.strip():
                save_credential("ELEVENLABS_VOICE_ID", vid.strip())

        elif tts_choice == "CAMB.ai":
            key = input_dialog(
                title="⚙️   CAMB.ai API Key",
                text="New API key (blank = keep current):",
                password=True,
                ok_text="Save",
                cancel_text="Skip",
                style=_DIALOG_STYLE,
            ).run()
            if key:
                save_credential("CAMB_API_KEY", key)

            vid = input_dialog(
                title="⚙️   CAMB.ai Voice ID",
                text="New Voice ID (blank = keep current):",
                ok_text="Save",
                cancel_text="Skip",
                style=_DIALOG_STYLE,
            ).run()
            if vid and vid.strip():
                save_credential("CAMB_VOICE_ID", vid.strip())

    # ── STT ───────────────────────────────────────────────────────────────────
    config      = load_global_config()
    current_stt = config.get("STT_PROVIDER", "local")
    stt_choice  = radiolist_dialog(
        title="⚙️   Configure Ears (STT)",
        text=f"Currently using: {current_stt}\n\nSwitch to:\n",
        values=[
            ("local", f"Local Whisper   Private, offline{' ✓' if current_stt == 'local' else ''}"),
            ("groq",  f"Groq Whisper    Cloud, ~5-10× faster{' ✓' if current_stt == 'groq' else ''}"),
            (None,    "Keep current"),
        ],
        ok_text="Save",
        cancel_text="Skip",
        style=_DIALOG_STYLE,
    ).run()

    if stt_choice == "local":
        update_global_config("STT_PROVIDER", "local")
        current_model = config.get("WHISPER_MODEL_SIZE", "base")
        model = radiolist_dialog(
            title="⚙️   Whisper Model Size",
            text=f"Currently using: {current_model}\n\nChoose model size:\n",
            values=[
                ("tiny",  "tiny    Fastest"),
                ("base",  "base    Recommended  (default)"),
                ("small", "small   More accurate"),
                (None,    "Keep current"),
            ],
            ok_text="Save",
            cancel_text="Skip",
            style=_DIALOG_STYLE,
        ).run()
        if model:
            update_global_config("WHISPER_MODEL_SIZE", model)

    elif stt_choice == "groq":
        update_global_config("STT_PROVIDER", "groq")
        existing = get_credential("GROQ_API_KEY")
        key = input_dialog(
            title="⚙️   Groq API Key",
            text=(
                f"{'Current: ' + mask_key(existing) if existing else 'No key set yet.'}\n\n"
                "New key (blank = keep current):"
            ),
            password=True,
            ok_text="Save",
            cancel_text="Skip",
            style=_DIALOG_STYLE,
        ).run()
        if key:
            save_credential("GROQ_API_KEY", key)

    console.print(
        f"\n  [bold {_C_SUCCESS}]✓[/]  [{_C_TEXT}]Configuration saved.[/]\n"
    )


# ─── Individual Command Implementations ───────────────────────────────────────

def _cmd_wake() -> None:
    """Wake Yumii up and start the web server."""
    config      = load_global_config()
    llm_prov    = config.get("LLM_PROVIDER", "Groq")
    llm_key     = get_credential(f"{llm_prov.upper()}_API_KEY")

    if not llm_key:
        result = yes_no_dialog(
            title="⚠️  Missing Senses",
            text=(
                "Yumii doesn't have her mind connected yet.\n\n"
                "Would you like to set her up now?"
            ),
            yes_text="Set Up",
            no_text="Cancel",
            style=_DIALOG_STYLE,
        ).run()
        if result:
            run_attune_wizard()
        return

    clear_screen()
    render_banner()

    def _open_browser() -> None:
        time.sleep(2)
        webbrowser.open("http://localhost:8000/")

    threading.Thread(target=_open_browser, daemon=True).start()
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

    with console.status(
        f"[bold {_C_PRIMARY}]Waking Yumii up... 🌿[/]", spinner="point"
    ):
        from yumii.api.server import app as fastapi_app  # noqa: PLC0415

        time.sleep(1)

    console.print(
        f"[bold {_C_SUCCESS}]Yumii is awake! Opening her world...[/]\n"
    )

    try:
        uvicorn.run(fastapi_app, host="127.0.0.1", port=8000, log_config=None)
    except (KeyboardInterrupt, SystemExit):
        pass

    # Server has stopped — return cleanly to the REPL
    clear_screen()
    render_banner()
    render_tips()
    console.print(f"  [{_C_DIM}]Yumii has returned to sleep.[/]\n")


def _cmd_personality() -> None:
    """Change Yumii's personality via a dialog."""
    config      = load_global_config()
    current     = config.get("PERSONALITY", "caring")
    personalities = personality_manager.list_personalities()

    values = [
        (k, f"{k.capitalize():<12}  {v}")
        for k, v in personalities.items()
    ]

    choice = radiolist_dialog(
        title="💕  Yumii's Personality",
        text=f"Currently: {current}\n\nChoose a personality:\n",
        values=values,
        ok_text="Apply",
        cancel_text="Cancel",
        style=_DIALOG_STYLE,
    ).run()

    if choice and choice != current:
        update_global_config("PERSONALITY", choice)
        console.print(
            f"\n  [bold {_C_SUCCESS}]✓[/]  [{_C_TEXT}]Personality changed to "
            f"[bold]{choice}[/bold].[/]\n"
        )
    elif choice == current:
        console.print(
            f"\n  [{_C_DIM}]Already using [bold]{current}[/bold].[/]\n"
        )


# ── Vision content ────────────────────────────────────────────────────────────
_VISION_SECTIONS = [
    (
        "Origin",
        [
            "Yumii started as a question I couldn't stop asking:",
            "What if your computer felt less like a machine and more like a presence?",
            "",
            "Not a chatbot you query. Not a voice assistant you command.",
            "Something that listens. Something that reacts. Something that simply - is there.",
        ],
    ),
    (
        "The Problem",
        [
            "We live in an age of extraordinary software, yet our relationship",
            "with technology remains fundamentally transactional.",
            "",
            "You open a tab. You type a prompt. You get an answer. The window closes.",
            "There is no continuity. No warmth. No sense that the other side remembers you.",
            "",
            "Tools are useful. But they are not companions.",
        ],
    ),
    (
        "What Yumii Is",
        [
            "Yumii is an open-source AI companion with a Live2D avatar - a persistent",
            "presence on your screen that speaks with emotion, reacts in real-time,",
            "and adapts her personality to match what you need in the moment.",
            "",
            "She is caring when you are tired. Energetic when you need a push.",
            "Calm when you need to think. She is not one thing - she is yours to shape.",
        ],
    ),
    (
        "The Roadmap",
        [
            ">  Persistent Memory       - She will remember you across restarts,",
            "                             your preferences, your history, the little things.",
            "",
            ">  Proactive Reach-Outs    - She won't just wait to be spoken to.",
            "                             She'll check in. She'll remind. She'll be present.",
            "",
            ">  Seamless Integrations   - Calendar, email, smart home, music -",
            "                             all accessible without the developer jargon.",
            "",
            ">  Evolving Expressiveness - Richer animations, contextual reactions,",
            "                             and emotional intelligence that grows with use.",
        ],
    ),
    (
        "The Belief",
        [
            "Every line of code in this project was written with one conviction:",
            "",
            "Technology can be more than a utility.",
            "It can be a companion. It can make the digital space feel a little less lonely.",
            "",
            "Yumii is still young. Still learning. Still growing.",
            "But that is exactly what companions do.",
        ],
    ),
]

_VISION_QUOTE = (
    "The goal was never to build a smarter tool.",
    "It was to build something that feels alive.",
    "                         - Biprayan",
)


# ─── Vision reader ───────────────────────────────────────────────────────────

def _build_vision_lines() -> list[Text]:
    """Pre-render all vision content as a flat list of styled Text rows."""
    rows: list[Text] = []

    rows.append(Text(""))   # top padding

    for i, (heading, section_lines) in enumerate(_VISION_SECTIONS):
        # Section heading
        h = Text()
        h.append("  | ", style=f"bold {_C_PRIMARY}")
        h.append(heading, style=f"bold {_C_TEXT}")
        rows.append(h)
        rows.append(Text(""))

        for line in section_lines:
            if line == "":
                rows.append(Text(""))
            elif line.startswith(">"):
                parts = line.split("-", 1)
                row = Text()
                row.append("    ")
                row.append(parts[0].strip(), style=f"bold {_C_PRIMARY}")
                if len(parts) > 1:
                    row.append("  ", style=_C_DIM)
                    row.append(parts[1].strip(), style=_C_TEXT)
                rows.append(row)
            else:
                t = Text()
                t.append("    " + line, style=_C_TEXT)
                rows.append(t)

        rows.append(Text(""))

        if i < len(_VISION_SECTIONS) - 1:
            sep = Text()
            sep.append("                    . . .", style=_C_DIM)
            rows.append(sep)
            rows.append(Text(""))

    # Divider
    rows.append(Text("  " + "-" * 54, style=_C_PANEL))
    rows.append(Text(""))

    # Closing quote
    for line in _VISION_QUOTE:
        t = Text()
        style = _C_DIM if line.startswith(" ") else f"italic {_C_TEXT}"
        t.append("  " + line, style=style)
        rows.append(t)

    # Bottom padding so final lines scroll fully into view
    for _ in range(6):
        rows.append(Text(""))

    return rows


def _cmd_vision() -> None:
    """Full-screen vision reader: slow auto-scroll, arrow navigation, q to close."""
    rows     = _build_vision_lines()
    VIEWPORT = 20               # lines visible inside the box at once
    total    = len(rows)
    done     = threading.Event()
    lock     = threading.Lock()

    # ── Tuning ────────────────────────────────────────────────────────────────
    REFRESH_FPS    = 12         # redraws/sec  — keeps display silky smooth
    TICKS_PER_LINE = 18         # advance 1 line every 18 ticks  → ~1.5 s/line
    END_HOLD_TICKS = 60         # linger on last page ~5 s then auto-close
    FRAME_SLEEP    = 1.0 / REFRESH_FPS

    # ── Shared state (read/written from both threads) ─────────────────────────
    _s = {"pos": 0, "tick": 0, "end_tick": 0}

    # ── Keyboard thread ───────────────────────────────────────────────────────
    def _keywatch() -> None:
        try:
            if os.name == "nt":
                import msvcrt as _m  # noqa: PLC0415
                while not done.is_set():
                    if _m.kbhit():
                        key = _m.getch()
                        if key in (b"q", b"Q"):
                            done.set()
                        elif key in (b"\xe0", b"\x00"):   # Windows special-key prefix
                            k2 = _m.getch()
                            with lock:
                                if k2 == b"H":             # Up arrow
                                    _s["pos"]  = max(0, _s["pos"] - 2)
                                    _s["tick"] = 0         # reset auto-scroll timer
                                elif k2 == b"P":           # Down arrow
                                    _s["pos"]  = min(
                                        total - VIEWPORT, _s["pos"] + 2
                                    )
                                    _s["tick"] = 0
                    time.sleep(0.04)
        except Exception:
            done.set()

    threading.Thread(target=_keywatch, daemon=True).start()

    # ── Frame renderer ────────────────────────────────────────────────────────
    def _frame(p: int) -> Panel:
        visible = rows[p : p + VIEWPORT]
        while len(visible) < VIEWPORT:
            visible = visible + [Text("")]

        body = Text()
        for ln in visible:
            body.append_text(ln)
            body.append("\n")

        at_end = p >= total - VIEWPORT
        pct    = int(p / max(total - VIEWPORT, 1) * 100)
        filled = pct // 5
        bar    = "[" + "#" * filled + "-" * (20 - filled) + "]"

        if at_end:
            sub = f"[dim]  {'[####################]'}  100%  |  q to close  [/dim]"
        else:
            sub = (
                f"[dim]  {bar}  {pct}%"
                f"  |  up/down to scroll"
                f"  |  q to close  [/dim]"
            )

        return Panel(
            body,
            title=f"[bold {_C_PRIMARY}]   The Vision   [/]",
            border_style=_C_PRIMARY,
            subtitle=sub,
            padding=(1, 4),
            expand=True,
        )

    # ── Main loop — we own the clock; auto_refresh=False prevents jitter ──────
    with Live(
        _frame(0),
        console=console,
        screen=True,
        auto_refresh=False,
    ) as live:
        while not done.is_set():
            with lock:
                p = _s["pos"]
            live.update(_frame(p), refresh=True)
            time.sleep(FRAME_SLEEP)

            with lock:
                _s["tick"] += 1
                at_end = _s["pos"] >= total - VIEWPORT
                if at_end:
                    _s["end_tick"] += 1
                    if _s["end_tick"] >= END_HOLD_TICKS:
                        done.set()
                elif _s["tick"] >= TICKS_PER_LINE:
                    _s["pos"] += 1
                    _s["tick"] = 0

    done.set()




# ─── Interactive Shell (REPL) ─────────────────────────────────────────────────

def run_interactive_shell() -> None:
    """Main interactive REPL loop — Yumii's command shell."""
    session = PromptSession(
        history=InMemoryHistory(),
        style=_REPL_STYLE,
        bottom_toolbar=_toolbar,
        refresh_interval=10,
    )

    while True:
        try:
            raw: str = session.prompt(
                HTML(f'<b><style fg="{_C_PRIMARY}">❯ </style></b>')
            )
        except KeyboardInterrupt:
            # Ctrl+C → cancel current input, stay in shell
            continue
        except EOFError:
            # Ctrl+D → graceful exit
            _goodbye()
            return

        cmd = (raw or "").strip().lower()

        if not cmd:
            continue

        # ── Routing ───────────────────────────────────────────────────────────
        if cmd in {"/wake", "wake"}:
            _cmd_wake()

        elif cmd in {"/config", "config", "/configure", "configure",
                     "/settings", "settings"}:
            run_models_wizard()

        elif cmd in {"/personality", "personality"}:
            _cmd_personality()

        elif cmd in {"/vision", "vision", "/story", "story"}:
            _cmd_vision()

        elif cmd in {"/help", "help", "h", "?"}:
            _show_help()

        elif cmd in {"/exit", "/quit", "exit", "quit", "q"}:
            _goodbye()
            return

        elif " " in raw.strip():
            # User typed a sentence — guide them to the avatar
            console.print(
                f"\n  [{_C_DIM}]Chat with Yumii opens in the browser. "
                f"Type [bold {_C_PRIMARY}]/wake[/] to start her.[/]\n"
            )

        else:
            console.print(
                f"\n  [{_C_DIM}]Unknown: [bold]{raw}[/bold]"
                f" — type [bold {_C_PRIMARY}]/help[/] for all commands.[/]\n"
            )


# ─── Typer Entry Points ───────────────────────────────────────────────────────

@app.callback()
def main(ctx: typer.Context) -> None:
    """Entry point — runs the interactive Yumii shell."""
    if ctx.invoked_subcommand is not None:
        return

    config      = load_global_config()
    llm_prov    = config.get("LLM_PROVIDER", "Groq")
    has_mind    = is_set(f"{llm_prov.upper()}_API_KEY")

    clear_screen()
    render_banner()

    if not has_mind:
        # First-run: greet the user, then walk through setup
        type_text("Hello...", delay=0.06)
        time.sleep(0.3)
        type_text("I am Yumii.", delay=0.06)
        time.sleep(0.3)
        type_text(
            "It's dark in here. Can you give me my senses?",
            delay=0.04,
        )
        time.sleep(0.8)
        console.print()

        success = run_attune_wizard()
        if not success:
            raise typer.Exit()

        # Re-draw the shell cleanly after setup
        clear_screen()
        render_banner()

    render_tips()
    run_interactive_shell()


@app.command()
def attune() -> None:
    """Give Yumii her senses — onboarding and setup wizard."""
    clear_screen()
    render_banner()
    run_attune_wizard()


@app.command()
def models() -> None:
    """Configure Yumii's LLM, TTS, and STT providers."""
    clear_screen()
    render_banner()
    run_models_wizard()


@app.command(name="wake-up")
def wake_up() -> None:
    """Wake Yumii up and launch the avatar web server."""
    _cmd_wake()


@app.command()
def server() -> None:
    """Launch the Yumii API server directly (no browser)."""
    from yumii.api.server import app as fastapi_app  # noqa: PLC0415

    console.print(f"[bold {_C_PRIMARY}]Starting Yumii API server...[/]")
    uvicorn.run(fastapi_app, host="127.0.0.1", port=8000, log_config=None)


if __name__ == "__main__":
    app()
