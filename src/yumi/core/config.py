from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os
from yumi.core.global_config import load_global_config
from yumi.core.credential_store import load_all as load_all_credentials

# ---------------------------------------------------------------------------
# 1. Preferences — non-sensitive settings from ~/.yumi/config.json
# ---------------------------------------------------------------------------
_prefs = load_global_config()
for key, value in _prefs.items():
    os.environ[key] = value

# ---------------------------------------------------------------------------
# 2. Credentials — secrets from the OS keychain (always take priority)
#    These overwrite any preference-level env vars so the keychain is
#    always the authoritative source for API keys.
# ---------------------------------------------------------------------------
_creds = load_all_credentials()
for key, value in _creds.items():
    os.environ[key] = value


class Settings(BaseSettings):
    elevenlabs_api_key:  str | None = Field(default=None, alias='ELEVENLABS_API_KEY')
    elevenlabs_voice_id: str | None = Field(default=None, alias='ELEVENLABS_VOICE_ID')
    llm_provider:        str        = Field(default="Groq",   alias='LLM_PROVIDER')
    groq_api_key:        str | None = Field(default=None, alias='GROQ_API_KEY')
    openai_api_key:      str | None = Field(default=None, alias='OPENAI_API_KEY')
    anthropic_api_key:   str | None = Field(default=None, alias='ANTHROPIC_API_KEY')
    personality:         str        = Field(default="caring", alias='PERSONALITY')

    # No env_file — project-local .env files must never shadow user config.
    # All values come from os.environ (populated above from keychain + config.json).
    model_config = SettingsConfigDict(extra='ignore')


settings = Settings()
