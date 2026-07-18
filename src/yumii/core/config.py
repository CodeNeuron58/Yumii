"""Central Pydantic settings for Yumii, loaded from ~/.yumii/config.json + auth.json via env."""

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from yumii.core.credential_store import load_all as load_all_credentials
from yumii.core.global_config import load_global_config

_prefs = load_global_config()
for key, value in _prefs.items():
    # Only scalar prefs go in the environment; structured config (MCP_SERVERS) is read from file.
    if isinstance(value, str):
        os.environ[key] = value

# Credentials from auth.json overwrite the env vars above (authoritative for API keys).
_creds = load_all_credentials()
for key, value in _creds.items():
    os.environ[key] = value


class Settings(BaseSettings):
    """Application settings, read from env (populated from auth.json + config.json)."""

    # Fresh install: everything local except the LLM (Kokoro voice, local Whisper, bundled VAD).
    tts_provider: str = Field(default="Kokoro", alias="TTS_PROVIDER")
    elevenlabs_api_key: str | None = Field(default=None, alias="ELEVENLABS_API_KEY")
    elevenlabs_voice_id: str | None = Field(default=None, alias="ELEVENLABS_VOICE_ID")
    camb_api_key: str | None = Field(default=None, alias="CAMB_API_KEY")
    camb_voice_id: str | None = Field(default=None, alias="CAMB_VOICE_ID")
    # fp32 default: int8 measured ~3.7x slower on x86 (slow quantized kernels).
    kokoro_voice: str = Field(default="af_heart", alias="KOKORO_VOICE")
    kokoro_model_size: str = Field(default="fp32", alias="KOKORO_MODEL_SIZE")
    llm_provider: str = Field(default="Ollama", alias="LLM_PROVIDER")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="qwen/qwen3.6-27b", alias="GROQ_MODEL")
    composio_api_key: str | None = Field(default=None, alias="COMPOSIO_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    # Ollama Cloud: key from ollama.com + a cloud model; base_url can point at a local Ollama.
    ollama_api_key: str | None = Field(default=None, alias="OLLAMA_API_KEY")
    ollama_model: str = Field(default="minimax-m3", alias="OLLAMA_MODEL")
    ollama_base_url: str = Field(default="https://ollama.com", alias="OLLAMA_BASE_URL")
    personality: str = Field(default="caring", alias="PERSONALITY")
    stt_provider: str = Field(default="local", alias="STT_PROVIDER")
    whisper_model_size: str = Field(default="base", alias="WHISPER_MODEL_SIZE")
    vosk_model_size: str = Field(default="small", alias="VOSK_MODEL_SIZE")
    # hitl_mode: never (no gate) | external (gate EXTERNAL tools) | always (gate all).
    hitl_mode: str = Field(default="external", alias="HITL_MODE")
    hitl_timeout_seconds: float = Field(default=30.0, alias="HITL_TIMEOUT_SECONDS")
    project_root: str = Field(default=".", description="Root directory of the project")

    # No env_file — a project-local .env must never shadow user config.
    model_config = SettingsConfigDict(extra="ignore")


settings = Settings()
