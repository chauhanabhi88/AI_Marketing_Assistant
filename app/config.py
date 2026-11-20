"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "ai_marketing_db"
    DB_USER: str = "root"
    DB_PASSWORD: str = ""

    # JWT
    JWT_SECRET_KEY: str = "change-this-secret-in-production-use-32-chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Gemini
    GEMINI_API_KEY: str = "AIzaSyAQ_tyRqs9r8VlSjR7t7DLmEitD3QlmGC0"
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # App
    APP_NAME: str = "AI Marketing Strategy Assistant"
    DEBUG: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
