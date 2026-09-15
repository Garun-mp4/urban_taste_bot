from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    telegram_bot_token: SecretStr = Field(validation_alias="TELEGRAM_BOT_TOKEN")
    admin_chat_id: int = Field(validation_alias="ADMIN_CHAT_ID")

    openai_api_key: SecretStr = Field(validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")

    database_url: str = Field(
        default="postgresql+asyncpg://urban_taste:change_me@localhost:5432/urban_taste",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")

    timezone: str = Field(default="Europe/Moscow", validation_alias="TIMEZONE")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    ai_history_limit: int = Field(default=12, ge=2, le=50, validation_alias="AI_HISTORY_LIMIT")
    ai_timeout_seconds: float = Field(default=45.0, gt=1, le=120, validation_alias="AI_TIMEOUT_SECONDS")
    db_pool_size: int = Field(default=10, ge=1, le=50, validation_alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, ge=0, le=100, validation_alias="DB_MAX_OVERFLOW")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
