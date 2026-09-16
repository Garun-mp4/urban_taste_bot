import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.admin_access import is_admin_callback, is_admin_message
from app.bot.keyboards.admin import request_actions_keyboard
from app.bot.keyboards.admin_panel import AdminListView, admin_request_keyboard
from app.bot.states import AdminStates
from app.config import Settings
from app.database.models import MessageRole, RequestEventType, RequestStatus
from app.services.container import ServiceContainer
from app.services.notifications import format_request_message, status_label
from app.services.request_view import format_request_details

logger = logging.getLogger(__name__)
router = Router(name="admin")


async def _restore_panel_after_reply(
    message: Message,
    data: dict[str, object],
    request_id: int,
    session: AsyncSession,
    services: ServiceContainer,
) -> None:
    """Return an admin to the request card after a panel reply is queued."""

    try:
        panel_message_id = int(data["panel_message_id"])
        panel_chat_id = int(data["panel_chat_id"])
        view = AdminListView(str(data["panel_view"]))
        page = int(data["panel_page"])
    except (KeyError, TypeError, ValueError):
        return

    request = await services.requests.get_by_id(session, request_id)
    if request is None:
        return
    events = await services.requests.get_events(session, request_id)
    try:
        await message.bot.edit_message_text(
            chat_id=panel_chat_id,
            message_id=panel_message_id,
            text=format_request_details(request, events),
            reply_markup=admin_request_keyboard(
                request.id,
                request.status,
                request.request_type,
                view=view,
                page=page,
            ),
        )
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).casefold():
            raise


@router.message(Command("stats"))
async def stats_private_chat_guard(
    message: Message,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if not is_admin_message(message, settings):
        return
    stats = await services.requests.get_stats(session)
    await message.answer(
        "Статистика Urban Taste\n\n"
        f"Пользователей: {stats.users_total}\n"
        f"Всего заявок: {stats.requests_total}\n"
        f"Новых заявок: {stats.new_requests}\n"
        f"Броней на сегодня: {stats.today_reservations}\n"
        f"В работе: {stats.in_progress_requests}\n"
        f"Завершённых: {stats.done_requests}\n"
        f"Отклонённых: {stats.rejected_requests}\n"
        f"Отменённых клиентом: {stats.cancelled_requests}\n\n"
        f"Ожидают доставки: {stats.pending_deliveries}\n"
        f"Ошибок доставки: {stats.failed_deliveries}"
    )


@router.message(Command("new_requests"))
async def new_requests_private_chat_guard(
    message: Message,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if not is_admin_message(message, settings):
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


@router.message(Command("requests"))
async def list_requests(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if not is_admin_message(message, settings):
        return

    raw_args = (command.args or "").strip()
    status: RequestStatus | None = None
    search: str | None = None
    if raw_args:
        first, *rest = raw_args.split(maxsplit=1)
        try:
            status = RequestStatus(first.upper())
        except ValueError:
            search = raw_args
        else:
            search = rest[0] if rest else None

    requests = await services.requests.get_latest(
        session,
        limit=10,
        status=status,
        search=search,
    )
    if not requests:
        filters = []
        if status is not None:
            filters.append(f"статус: {status_label(status.value)}")
        if search:
            filters.append(f"поиск: {search[:100]}")
        suffix = f" ({', '.join(filters)})" if filters else ""
        await message.answer(f"Заявок не найдено{suffix}.")
        return

    title = "Последние заявки Urban Taste"
    if status is not None or search:
        title += " по фильтру"
    await message.answer(f"{title}: {len(requests)}")
    for request in requests:
        keyboard = request_actions_keyboard(request.id, request.status, request.request_type)
        await message.answer(
            format_request_message(request),
            reply_markup=keyboard if keyboard.inline_keyboard else None,
        )


@router.message(Command("request"))
async def show_request(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if not is_admin_message(message, settings):
        return
    raw_request_id = (command.args or "").strip()
    try:
        request_id = int(raw_request_id)
    except (TypeError, ValueError):
        await message.answer("Использование: /request <ID заявки>")
        return
    request = await services.requests.get_by_id(session, request_id)
    if request is None:
        await message.answer("Заявка не найдена.")
        return
    events = await services.requests.get_events(session, request_id)
    keyboard = request_actions_keyboard(request.id, request.status, request.request_type)
    await message.answer(
        format_request_details(request, events),
        reply_markup=keyboard if keyboard.inline_keyboard else None,
    )


@router.callback_query(F.data.startswith("request_status:"))
async def update_request_status(
    callback: CallbackQuery,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if not is_admin_callback(callback, settings):
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
        request = await services.requests.update_status(
            session,
            request_id,
            status,
            actor_telegram_id=callback.from_user.id if callback.from_user else None,
        )
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    if request is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    status_changed = request.status != previous_status
    if status_changed:
        await services.notifications.enqueue_client_status(session, request)

    keyboard = request_actions_keyboard(request.id, request.status, request.request_type)
    if status_changed and callback.message is not None:
        try:
            await callback.message.edit_text(
                format_request_message(request),
                reply_markup=keyboard if keyboard.inline_keyboard else None,
            )
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc).casefold():
                raise
    await callback.answer(
        f"Статус: {status_label(request.status)}"
        if status_changed
        else f"Статус уже: {status_label(request.status)}"
    )
    logger.info("Request status updated: request_id=%s status=%s", request.id, request.status)


@router.callback_query(F.data.startswith("request_reply:"))
async def start_admin_reply(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if not is_admin_callback(callback, settings):
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
    if not is_admin_message(message, settings):
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
    if request.status in {
        RequestStatus.DONE.value,
        RequestStatus.REJECTED.value,
        RequestStatus.CANCELLED.value,
    }:
        await state.clear()
        await message.answer("Заявка уже закрыта. Ответ отправить нельзя.")
        return

    reply_text = text[:4000]
    await services.notifications.enqueue_client_reply(
        session,
        request,
        reply_text,
        idempotency_key=str(message.message_id),
    )
    await services.requests.add_event(
        session,
        request.id,
        event_type=RequestEventType.ADMIN_REPLY,
        actor_telegram_id=message.from_user.id if message.from_user else None,
        note=reply_text,
    )
    await services.conversations.add_message(session, request.user.id, MessageRole.ASSISTANT, reply_text)
    await state.clear()
    await message.answer(f"Ответ по заявке #{request_id} поставлен в очередь на отправку клиенту.")
    await _restore_panel_after_reply(message, data, request_id, session, services)
