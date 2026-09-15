from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import RequestStatus, RequestType


def request_actions_keyboard(
    request_id: int,
    status: str,
    request_type: str | None = None,
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    if status == RequestStatus.NEW.value:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="В работу",
                    callback_data=f"request_status:{request_id}:{RequestStatus.IN_PROGRESS.value}",
                )
            ]
        )
    if status in {RequestStatus.NEW.value, RequestStatus.IN_PROGRESS.value}:
        action_text = "✅ Подтвердить" if request_type == RequestType.RESERVATION.value else "✅ Завершить"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=action_text,
                    callback_data=f"request_status:{request_id}:{RequestStatus.DONE.value}",
                )
            ]
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    text="⛔ Отклонить",
                    callback_data=f"request_status:{request_id}:{RequestStatus.REJECTED.value}",
                )
            ]
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    text="💬 Ответить клиенту",
                    callback_data=f"request_reply:{request_id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)
