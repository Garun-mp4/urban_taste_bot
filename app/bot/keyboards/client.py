from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import RequestStatus


def client_request_keyboard(request_id: int, status: str) -> InlineKeyboardMarkup | None:
    if status not in {RequestStatus.NEW.value, RequestStatus.IN_PROGRESS.value}:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отменить заявку",
                    callback_data=f"client_request:cancel:{request_id}",
                )
            ]
        ]
    )
