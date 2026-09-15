import logging

from aiogram import Bot

from app.bot.keyboards.admin import request_actions_keyboard
from app.database.models import ClientRequest, RequestType

logger = logging.getLogger(__name__)


def format_request_message(request: ClientRequest) -> str:
    if request.request_type == RequestType.RESERVATION.value:
        reservation_date = (
            request.reservation_date.strftime("%d.%m.%Y") if request.reservation_date else "не указана"
        )
        reservation_time = (
            request.reservation_time.strftime("%H:%M") if request.reservation_time else "не указано"
        )
        return (
            "Новая заявка на бронирование\n\n"
            f"ID: {request.id}\n"
            f"Клиент: {request.customer_name}\n"
            f"Телефон: {request.phone or 'не указан'}\n"
            f"Дата: {reservation_date} {reservation_time}\n"
            f"Количество гостей: {request.guests or 'не указано'}\n"
            f"Статус: {request.status}"
        )

    return (
        "Новое обращение клиента\n\n"
        f"ID: {request.id}\n"
        f"Клиент: {request.customer_name}\n"
        f"Телефон: {request.phone or 'не указан'}\n"
        f"Вопрос: {(request.details or 'не указан')[:2500]}\n"
        f"Статус: {request.status}"
    )


class AdminNotificationService:
    def __init__(self, bot: Bot, admin_chat_id: int) -> None:
        self._bot = bot
        self._admin_chat_id = admin_chat_id

    async def send_request(self, request: ClientRequest) -> None:
        await self._bot.send_message(
            chat_id=self._admin_chat_id,
            text=format_request_message(request),
            reply_markup=request_actions_keyboard(request.id, request.status),
        )
        logger.info("Admin notification sent for request_id=%s", request.id)
