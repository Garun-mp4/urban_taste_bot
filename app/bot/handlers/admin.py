import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.admin import request_actions_keyboard
from app.config import Settings
from app.database.models import RequestStatus
from app.services.container import ServiceContainer
from app.services.notifications import format_request_message

logger = logging.getLogger(__name__)
router = Router(name="admin")


@router.message(Command("stats"))
async def stats_private_chat_guard(
    message: Message,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    # This handler is deliberately kept separate from the actual admin filter
    # so a command from any other private chat receives no business data.
    if message.chat.id != settings.admin_chat_id:
        return
    stats = await services.requests.get_stats(session)
    await message.answer(
        "Статистика Urban Taste\n\n"
        f"Пользователей: {stats.users_total}\n"
        f"Всего заявок: {stats.requests_total}\n"
        f"Новых заявок: {stats.new_requests}"
    )


@router.message(Command("new_requests"))
async def new_requests_private_chat_guard(
    message: Message,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if message.chat.id != settings.admin_chat_id:
        return
    requests = await services.requests.get_latest(session, limit=10)
    if not requests:
        await message.answer("Новых заявок пока нет.")
        return
    await message.answer(f"Последние заявки Urban Taste: {len(requests)}")
    for request in requests:
        keyboard = request_actions_keyboard(request.id, request.status)
        await message.answer(
            format_request_message(request),
            reply_markup=keyboard if keyboard.inline_keyboard else None,
        )


@router.callback_query(F.data.startswith("request_status:"))
async def update_request_status(
    callback: CallbackQuery,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if callback.message is None or callback.message.chat.id != settings.admin_chat_id:
        await callback.answer("Недоступно", show_alert=True)
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer("Некорректная команда", show_alert=True)
        return
    try:
        request_id = int(parts[1])
        status = RequestStatus(parts[2])
    except (TypeError, ValueError):
        await callback.answer("Некорректная заявка", show_alert=True)
        return

    request = await services.requests.update_status(session, request_id, status)
    if request is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    keyboard = request_actions_keyboard(request.id, request.status)
    await callback.message.edit_text(
        format_request_message(request),
        reply_markup=keyboard if keyboard.inline_keyboard else None,
    )
    await callback.answer(f"Статус: {request.status}")
    logger.info("Request status updated: request_id=%s status=%s", request.id, request.status)
