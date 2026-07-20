from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    api_key: str
    github_token: str

    groq_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    huggingface_api_key: str = ""
    cloudflare_api_key: str = ""
    cloudflare_account_id: str = ""
    vercel_ai_gateway_key: str = ""

    cors_origins: list[str] = []


@lru_cache
def get_settings() -> Settings:
    return Settings()
