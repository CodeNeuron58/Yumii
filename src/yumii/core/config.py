"""Central configuration settings model for Yumii.

Loads values from the environment, pre-populated from the user's config
files: ~/.yumii/config.json (preferences) and ~/.yumii/auth.json (secrets).
"""

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from yumii.core.credential_store import load_all as load_all_credentials
from yumii.core.global_config import load_global_config

_prefs = load_global_config()
for key, value in _prefs.items():
    # Only scalar preferences belong in the environment. Structured
    # config (e.g. the MCP_SERVERS list) is read directly from the
    # file by its consumers — and os.environ rejects non-strings.
    if isinstance(value, str):
        os.environ[key] = value

# Credentials — secrets from ~/.yumii/auth.json (always take priority)
# These overwrite any preference-level env vars so auth.json is
# always the authoritative source for API keys.
_creds = load_all_credentials()
for key, value in _creds.items():
    os.environ[key] = value


class Settings(BaseSettings):
    """Pydantic settings model for the application configuration.

    Values are loaded from environment variables, which are pre-populated
    from auth.json (secrets) and config.json (preferences).
    """

    tts_provider: str = Field(default="ElevenLabs", alias="TTS_PROVIDER")
    elevenlabs_api_key: str | None = Field(default=None, alias="ELEVENLABS_API_KEY")
    elevenlabs_voice_id: str | None = Field(default=None, alias="ELEVENLABS_VOICE_ID")
    camb_api_key: str | None = Field(default=None, alias="CAMB_API_KEY")
    camb_voice_id: str | None = Field(default=None, alias="CAMB_VOICE_ID")
    # Kokoro (local TTS) — no API key; voice is a built-in voice name.
    # fp32 by default: the int8 variant measured ~3.7x SLOWER than fp32
    # on x86 (quantized ops fall back to slow kernels) — RTF 2.6 vs 0.7
    # on an i5-13500H. int8 stays available for machines where it wins.
    kokoro_voice: str = Field(default="af_heart", alias="KOKORO_VOICE")
    kokoro_model_size: str = Field(default="fp32", alias="KOKORO_MODEL_SIZE")
    llm_provider: str = Field(default="Groq", alias="LLM_PROVIDER")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    # Which Groq-hosted model runs the agent. qwen3.6-27b is the
    # default after live testing: cleaner tool calls than llama-3.3
    # (no explicit-null habit) and its own free-tier quota bucket.
    groq_model: str = Field(default="qwen/qwen3.6-27b", alias="GROQ_MODEL")
    # Composio (tool integrations): the API key is the only secret; the
    # enabled toolkit list lives as structured data in config.json.
    composio_api_key: str | None = Field(default=None, alias="COMPOSIO_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    # Ollama Cloud: an API key from ollama.com plus a cloud model name
    # (e.g. "gpt-oss:120b", "qwen3-coder:480b"). base_url defaults to
    # the cloud endpoint but can point at a local Ollama for offline use.
    ollama_api_key: str | None = Field(default=None, alias="OLLAMA_API_KEY")
    ollama_model: str = Field(default="gpt-oss:120b", alias="OLLAMA_MODEL")
    ollama_base_url: str = Field(default="https://ollama.com", alias="OLLAMA_BASE_URL")
    personality: str = Field(default="caring", alias="PERSONALITY")
    # STT configuration
    stt_provider: str = Field(default="local", alias="STT_PROVIDER")
    whisper_model_size: str = Field(default="base", alias="WHISPER_MODEL_SIZE")
    vosk_model_size: str = Field(default="small", alias="VOSK_MODEL_SIZE")

    # HITL (human-in-the-loop) confirmation gates
    # Valid values: "never" (no gate), "external" (gate only tools whose
    # ToolCategory is EXTERNAL or whose policy.requires_confirmation=True),
    # "always" (gate every tool call). Default "external".
    hitl_mode: str = Field(default="external", alias="HITL_MODE")
    hitl_timeout_seconds: float = Field(default=30.0, alias="HITL_TIMEOUT_SECONDS")

    # Project paths
    project_root: str = Field(default=".", description="Root directory of the project")

    # No env_file — project-local .env files must never shadow user config.
    # All values come from os.environ (populated above from auth.json + config.json).
    model_config = SettingsConfigDict(extra="ignore")


settings = Settings()
