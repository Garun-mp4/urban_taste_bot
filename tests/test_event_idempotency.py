from datetime import datetime

from aiogram.types import CallbackQuery, Chat, Message, User

from app.bot.middlewares.database import event_key


def test_message_event_key_is_scoped_to_chat():
    message = Message(
        message_id=17,
        date=datetime(2026, 9, 16, 10, 0),
        chat=Chat(id=42, type="private"),
    )

    assert event_key(message) == "message:42:17"


def test_callback_event_key_uses_telegram_callback_id():
    callback = CallbackQuery(
        id="callback-123",
        from_user=User(id=42, is_bot=False, first_name="Test"),
        chat_instance="instance-1",
    )

    assert event_key(callback) == "callback:callback-123"
