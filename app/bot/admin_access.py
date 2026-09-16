"""Authorization guards shared by Telegram administrator handlers."""

from aiogram.types import CallbackQuery, Message

from app.config import Settings


def is_admin_message(message: Message, settings: Settings) -> bool:
    return settings.is_admin(
        chat_id=message.chat.id,
        user_id=message.from_user.id if message.from_user else None,
        chat_type=message.chat.type,
    )


def is_admin_callback(callback: CallbackQuery, settings: Settings) -> bool:
    return callback.message is not None and settings.is_admin(
        chat_id=callback.message.chat.id,
        user_id=callback.from_user.id if callback.from_user else None,
        chat_type=callback.message.chat.type,
    )
