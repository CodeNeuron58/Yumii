"""Central configuration settings model for Yumi.

Loads values from the environment, preferring secrets mapped from the OS keychain.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os
from yumi.core.global_config import load_global_config
from yumi.core.credential_store import load_all as load_all_credentials

_prefs = load_global_config()
for key, value in _prefs.items():
    os.environ[key] = value

# Credentials — secrets from the OS keychain (always take priority)
# These overwrite any preference-level env vars so the keychain is
# always the authoritative source for API keys.
_creds = load_all_credentials()
for key, value in _creds.items():
    os.environ[key] = value


class Settings(BaseSettings):
    """Pydantic settings model for the application configuration.
    Values are loaded from environment variables, which are pre-populated
    from the OS keychain and user preferences.
    """

    tts_provider:        str        = Field(default="ElevenLabs", alias='TTS_PROVIDER')
    elevenlabs_api_key:  str | None = Field(default=None, alias='ELEVENLABS_API_KEY')
    elevenlabs_voice_id: str | None = Field(default=None, alias='ELEVENLABS_VOICE_ID')
    camb_api_key:        str | None = Field(default=None, alias='CAMB_API_KEY')
    camb_voice_id:       str | None = Field(default=None, alias='CAMB_VOICE_ID')
    llm_provider:        str        = Field(default="Groq",    alias='LLM_PROVIDER')
    groq_api_key:        str | None = Field(default=None, alias='GROQ_API_KEY')
    openai_api_key:      str | None = Field(default=None, alias='OPENAI_API_KEY')
    anthropic_api_key:   str | None = Field(default=None, alias='ANTHROPIC_API_KEY')
    personality:         str        = Field(default="caring",  alias='PERSONALITY')
    # STT configuration
    stt_provider:        str        = Field(default="local",   alias='STT_PROVIDER')
    whisper_model_size:  str        = Field(default="base",    alias='WHISPER_MODEL_SIZE')

    # Project paths
    project_root:         str        = Field(default=".", description="Root directory of the project")

    # No env_file — project-local .env files must never shadow user config.

    # No env_file — project-local .env files must never shadow user config.
    # All values come from os.environ (populated above from keychain + config.json).
    model_config = SettingsConfigDict(extra='ignore')


settings = Settings()
