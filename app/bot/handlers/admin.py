import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.admin import request_actions_keyboard
from app.config import Settings
from app.database.models import MessageRole, RequestStatus
from app.services.container import ServiceContainer
from app.services.notifications import format_request_message

logger = logging.getLogger(__name__)
router = Router(name="admin")


class AdminStates(StatesGroup):
    reply = State()


def _is_admin_message(message: Message, settings: Settings) -> bool:
    return settings.is_admin(
        chat_id=message.chat.id,
        user_id=message.from_user.id if message.from_user else None,
        chat_type=message.chat.type,
    )


def _is_admin_callback(callback: CallbackQuery, settings: Settings) -> bool:
    return callback.message is not None and settings.is_admin(
        chat_id=callback.message.chat.id,
        user_id=callback.from_user.id if callback.from_user else None,
        chat_type=callback.message.chat.type,
    )


@router.message(Command("stats"))
async def stats_private_chat_guard(
    message: Message,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if not _is_admin_message(message, settings):
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
    if not _is_admin_message(message, settings):
        return
    requests = await services.requests.get_latest(session, limit=10, status=RequestStatus.NEW)
    if not requests:
        await message.answer("Новых заявок пока нет.")
        return
    await message.answer(f"Новые заявки Urban Taste: {len(requests)}")
    for request in requests:
        keyboard = request_actions_keyboard(request.id, request.status, request.request_type)
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
    if not _is_admin_callback(callback, settings):
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

    request = await services.requests.get_by_id(session, request_id)
    if request is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    previous_status = request.status
    try:
        request = await services.requests.update_status(session, request_id, status)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    if request is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    if request.status != previous_status:
        await services.notifications.enqueue_client_status(session, request)

    keyboard = request_actions_keyboard(request.id, request.status, request.request_type)
    if callback.message is not None:
        await callback.message.edit_text(
            format_request_message(request),
            reply_markup=keyboard if keyboard.inline_keyboard else None,
        )
    await callback.answer(f"Статус: {request.status}")
    logger.info("Request status updated: request_id=%s status=%s", request.id, request.status)


@router.callback_query(F.data.startswith("request_reply:"))
async def start_admin_reply(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if not _is_admin_callback(callback, settings):
        await callback.answer("Недоступно", show_alert=True)
        return
    try:
        request_id = int((callback.data or "").split(":", 1)[1])
    except (TypeError, ValueError):
        await callback.answer("Некорректная заявка", show_alert=True)
        return
    request = await services.requests.get_by_id(session, request_id)
    if request is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    if request.status in {
        RequestStatus.DONE.value,
        RequestStatus.REJECTED.value,
        RequestStatus.CANCELLED.value,
    }:
        await callback.answer("Заявка уже закрыта", show_alert=True)
        return

    await state.clear()
    await state.update_data(request_id=request_id)
    await state.set_state(AdminStates.reply)
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(
            f"Напишите ответ клиенту по заявке #{request_id}. Для отмены: /cancel"
        )


@router.message(AdminStates.reply, Command("cancel"))
async def cancel_admin_reply(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Ответ клиенту отменён.")


@router.message(AdminStates.reply, F.text)
async def send_admin_reply(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if not _is_admin_message(message, settings):
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Ответ не должен быть пустым.")
        return
    data = await state.get_data()
    try:
        request_id = int(data["request_id"])
    except (KeyError, TypeError, ValueError):
        await state.clear()
        await message.answer("Сессия ответа устарела. Откройте заявку заново.")
        return

    request = await services.requests.get_by_id(session, request_id)
    if request is None or request.user is None:
        await state.clear()
        await message.answer("Заявка или клиент не найдены.")
        return
    try:
        await services.notifications.send_client_message(request, text[:4000])
    except Exception:
        logger.exception("Could not send admin reply for request_id=%s", request_id)
        await message.answer("Не удалось отправить ответ клиенту. Попробуйте ещё раз.")
        return

    await services.conversations.add_message(session, request.user.id, MessageRole.ASSISTANT, text[:4000])
    await state.clear()
    await message.answer(f"Ответ по заявке #{request_id} отправлен клиенту.")
