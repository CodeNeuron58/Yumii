from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    elevenlabs_api_key: str = Field(..., env='ELEVENLABS_API_KEY')
    groq_api_key: str = Field(..., env='GROQ_API_KEY')
    
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

settings = Settings()
