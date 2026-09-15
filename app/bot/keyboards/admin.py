from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import RequestStatus


def request_actions_keyboard(request_id: int, status: str) -> InlineKeyboardMarkup:
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
    if status != RequestStatus.DONE.value:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="Завершить",
                    callback_data=f"request_status:{request_id}:{RequestStatus.DONE.value}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)
