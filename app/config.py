from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    telegram_bot_token: SecretStr = Field(validation_alias="TELEGRAM_BOT_TOKEN")
    admin_chat_id: int = Field(validation_alias="ADMIN_CHAT_ID")
    admin_user_ids: str = Field(default="", validation_alias="ADMIN_USER_IDS")

    openai_api_key: SecretStr = Field(validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5.6-luna", validation_alias="OPENAI_MODEL")
    openai_reasoning_effort: str = Field(
        default="medium",
        validation_alias="OPENAI_REASONING_EFFORT",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://urban_taste:change_me@localhost:5432/urban_taste",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")

    timezone: str = Field(default="Europe/Moscow", validation_alias="TIMEZONE")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    drop_pending_updates: bool = Field(default=False, validation_alias="DROP_PENDING_UPDATES")
    rate_limit_seconds: float = Field(default=1.0, gt=0, le=60, validation_alias="RATE_LIMIT_SECONDS")
    notification_poll_seconds: float = Field(
        default=2.0,
        gt=0.5,
        le=60,
        validation_alias="NOTIFICATION_POLL_SECONDS",
    )
    notification_max_attempts: int = Field(
        default=10,
        ge=1,
        le=100,
        validation_alias="NOTIFICATION_MAX_ATTEMPTS",
    )
    reservation_capacity: int = Field(default=50, ge=1, le=1000, validation_alias="RESERVATION_CAPACITY")
    reservation_max_guests: int = Field(
        default=50,
        ge=1,
        le=1000,
        validation_alias="RESERVATION_MAX_GUESTS",
    )
    reservation_duration_minutes: int = Field(
        default=90,
        ge=30,
        le=360,
        validation_alias="RESERVATION_DURATION_MINUTES",
    )
    reservation_slot_interval_minutes: int = Field(
        default=30,
        ge=15,
        le=120,
        validation_alias="RESERVATION_SLOT_INTERVAL_MINUTES",
    )
    reservation_min_advance_minutes: int = Field(
        default=30,
        ge=0,
        le=1440,
        validation_alias="RESERVATION_MIN_ADVANCE_MINUTES",
    )
    reservation_max_days: int = Field(default=30, ge=1, le=365, validation_alias="RESERVATION_MAX_DAYS")
    processed_event_retention_days: int = Field(
        default=30,
        ge=1,
        le=365,
        validation_alias="PROCESSED_EVENT_RETENTION_DAYS",
    )
    ai_history_limit: int = Field(default=12, ge=2, le=50, validation_alias="AI_HISTORY_LIMIT")
    ai_history_char_limit: int = Field(
        default=24000,
        ge=2000,
        le=100000,
        validation_alias="AI_HISTORY_CHAR_LIMIT",
    )
    ai_timeout_seconds: float = Field(default=45.0, gt=1, le=120, validation_alias="AI_TIMEOUT_SECONDS")
    db_pool_size: int = Field(default=10, ge=1, le=50, validation_alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, ge=0, le=100, validation_alias="DB_MAX_OVERFLOW")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def validate_booking_limits(self) -> "Settings":
        if self.reservation_max_guests > self.reservation_capacity:
            raise ValueError("RESERVATION_MAX_GUESTS cannot exceed RESERVATION_CAPACITY")
        return self

    @property
    def admin_ids(self) -> frozenset[int]:
        """Return explicitly configured admin user IDs."""

        return frozenset(
            int(item.strip())
            for item in self.admin_user_ids.split(",")
            if item.strip().isdigit()
        )

    def is_admin(self, *, chat_id: int, user_id: int | None, chat_type: str | None) -> bool:
        """Validate both the configured admin chat and the acting Telegram user."""

        if chat_id != self.admin_chat_id or user_id is None:
            return False
        if self.admin_ids:
            return user_id in self.admin_ids
        return chat_type == "private" and user_id == chat_id


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
