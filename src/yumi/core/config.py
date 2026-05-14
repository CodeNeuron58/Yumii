from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os
from yumi.core.global_config import load_global_config

# We inject the global config into the environment before initializing Settings
# so that pydantic can pick it up if it's not in the local .env
_global_config = load_global_config()
for key, value in _global_config.items():
    if key not in os.environ:
        os.environ[key] = value

class Settings(BaseSettings):
    elevenlabs_api_key: str | None = Field(default=None, alias='ELEVENLABS_API_KEY')
    llm_provider: str = Field(default="Groq", alias='LLM_PROVIDER')
    groq_api_key: str | None = Field(default=None, alias='GROQ_API_KEY')
    openai_api_key: str | None = Field(default=None, alias='OPENAI_API_KEY')
    anthropic_api_key: str | None = Field(default=None, alias='ANTHROPIC_API_KEY')
    personality: str = Field(default="caring", alias='PERSONALITY')

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

settings = Settings()
