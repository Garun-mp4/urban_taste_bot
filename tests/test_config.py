from app.config import Settings


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "TELEGRAM_BOT_TOKEN": "test-token",
        "ADMIN_CHAT_ID": 42,
        "OPENAI_API_KEY": "test-key",
    }
    values.update(overrides)
    return Settings(**values)


def test_private_admin_chat_uses_chat_owner_as_fallback():
    settings = _settings()

    assert settings.is_admin(chat_id=42, user_id=42, chat_type="private")
    assert not settings.is_admin(chat_id=42, user_id=99, chat_type="private")


def test_admin_group_requires_explicit_user_ids():
    settings = _settings(ADMIN_USER_IDS="101, 202")

    assert settings.is_admin(chat_id=42, user_id=101, chat_type="supergroup")
    assert not settings.is_admin(chat_id=42, user_id=303, chat_type="supergroup")
    assert settings.is_admin(chat_id=42, user_id=101, chat_type="private")
    assert not settings.is_admin(chat_id=42, user_id=303, chat_type="private")
