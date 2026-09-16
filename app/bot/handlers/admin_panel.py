import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.admin_access import is_admin_callback, is_admin_message
from app.bot.keyboards.admin_panel import (
    ADMIN_PANEL_PAGE_SIZE,
    AdminListView,
    admin_home_keyboard,
    admin_request_keyboard,
    admin_request_list_keyboard,
    admin_stats_keyboard,
    admin_status_confirmation_keyboard,
)
from app.bot.states import AdminPanelStates, AdminStates
from app.config import Settings
from app.database.models import RequestStatus, RequestType
from app.services.container import ServiceContainer
from app.services.notifications import format_request_message, status_label
from app.services.request_view import format_request_details
from app.services.requests import RequestStats

logger = logging.getLogger(__name__)
router = Router(name="admin_panel")


def _today(settings: Settings) -> date:
    return datetime.now(ZoneInfo(settings.timezone)).date()


def _format_stats(stats: RequestStats) -> str:
    return (
        "📊 Статистика Urban Taste\n\n"
        f"Пользователей: {stats.users_total}\n"
        f"Всего заявок: {stats.requests_total}\n"
        f"Новых: {stats.new_requests}\n"
        f"В работе: {stats.in_progress_requests}\n"
        f"Броней сегодня: {stats.today_reservations}\n"
        f"Завершённых: {stats.done_requests}\n"
        f"Отклонённых: {stats.rejected_requests}\n"
        f"Отменённых клиентом: {stats.cancelled_requests}\n\n"
        f"В очереди доставки: {stats.pending_deliveries}\n"
        f"Ошибок доставки: {stats.failed_deliveries}"
    )


def _format_home(stats: RequestStats) -> str:
    return (
        "🛎 Админ-панель Urban Taste\n\n"
        "Рабочая очередь\n"
        f"Новые заявки: {stats.new_requests}\n"
        f"В работе: {stats.in_progress_requests}\n"
        f"Брони сегодня: {stats.today_reservations}\n"
        f"Ошибки доставки: {stats.failed_deliveries}\n\n"
        "Выберите раздел, чтобы перейти к действию."
    )


def _view_title(view: AdminListView, search_query: str | None = None) -> str:
    if view == AdminListView.NEW:
        return "🆕 Новые заявки"
    if view == AdminListView.TODAY:
        return "📅 Брони на сегодня"
    if view == AdminListView.QUESTIONS:
        return "💬 Вопросы клиентов"
    if view == AdminListView.SEARCH:
        return f"🔍 Поиск: {search_query or 'не указан'}"
    return "📋 Все заявки"


def _compact_request(request) -> str:
    request_kind = "Бронь" if request.request_type == RequestType.RESERVATION.value else "Вопрос"
    customer_name = " ".join(str(request.customer_name or "Без имени").split())
    if request.request_type == RequestType.RESERVATION.value:
        reservation_date = (
            request.reservation_date.strftime("%d.%m %H:%M")
            if request.reservation_date and request.reservation_time
            else "дата не указана"
        )
        details = f"{reservation_date} · {request.guests or '?'} гост."
    else:
        details = " ".join(str(request.details or "Вопрос не указан").split())[:150]
    return f"#{request.id} · {request_kind} · {status_label(request.status)}\n{customer_name}\n{details}"


def _format_request_list(
    view: AdminListView,
    requests: list,
    *,
    page: int,
    has_next: bool,
    search_query: str | None = None,
) -> str:
    lines = [f"{_view_title(view, search_query)} · страница {page + 1}", ""]
    if not requests:
        lines.append("Заявок в этом разделе нет.")
    else:
        for index, request in enumerate(requests):
            if index:
                lines.append("\n──────────")
            lines.append(_compact_request(request))
        if has_next:
            lines.extend(("", "Есть ещё заявки — используйте кнопку «Дальше»."))
    return "\n".join(lines)


def _parse_page(raw_page: str) -> int:
    page = int(raw_page)
    if not 0 <= page <= 1000:
        raise ValueError
    return page


async def _requests_for_view(
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
    state: FSMContext,
    view: AdminListView,
    page: int,
) -> tuple[list, str | None]:
    search_query: str | None = None
    status: RequestStatus | None = None
    request_type: RequestType | None = None
    reservation_date: date | None = None
    if view == AdminListView.NEW:
        status = RequestStatus.NEW
    elif view == AdminListView.TODAY:
        request_type = RequestType.RESERVATION
        reservation_date = _today(settings)
    elif view == AdminListView.QUESTIONS:
        request_type = RequestType.QUESTION
    elif view == AdminListView.SEARCH:
        data = await state.get_data()
        search_query = str(data.get("search_query", "")).strip()[:100]
        if not search_query:
            return [], None

    requests = await services.requests.get_latest(
        session,
        limit=ADMIN_PANEL_PAGE_SIZE + 1,
        status=status,
        request_type=request_type,
        reservation_date=reservation_date,
        search=search_query,
        offset=page * ADMIN_PANEL_PAGE_SIZE,
    )
    return requests, search_query


async def _edit_panel_message(
    message: Message,
    text: str,
    *,
    reply_markup=None,
) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).casefold():
            raise


async def _render_list(
    callback: CallbackQuery,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
    state: FSMContext,
    view: AdminListView,
    page: int,
) -> None:
    if callback.message is None:
        return
    requests, search_query = await _requests_for_view(
        session,
        services,
        settings,
        state,
        view,
        page,
    )
    has_next = len(requests) > ADMIN_PANEL_PAGE_SIZE
    visible_requests = requests[:ADMIN_PANEL_PAGE_SIZE]
    text = _format_request_list(
        view,
        visible_requests,
        page=page,
        has_next=has_next,
        search_query=search_query,
    )
    keyboard = admin_request_list_keyboard(
        [(request.id, request.customer_name) for request in visible_requests],
        view=view,
        page=page,
        has_next=has_next,
    )
    await _edit_panel_message(callback.message, text, reply_markup=keyboard)


@router.message(Command("admin"))
async def open_admin_panel(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if not is_admin_message(message, settings):
        return
    await state.clear()
    stats = await services.requests.get_stats(session)
    await message.answer(_format_home(stats), reply_markup=admin_home_keyboard())


@router.callback_query(F.data == "admin:home")
async def admin_home(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if not is_admin_callback(callback, settings):
        await callback.answer()
        return
    await callback.answer()
    await state.clear()
    if callback.message is None:
        return
    stats = await services.requests.get_stats(session)
    await _edit_panel_message(callback.message, _format_home(stats), reply_markup=admin_home_keyboard())


@router.callback_query(F.data == "admin:close")
async def close_admin_panel(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if not is_admin_callback(callback, settings):
        await callback.answer()
        return
    await callback.answer()
    await state.clear()
    if callback.message is not None:
        await _edit_panel_message(callback.message, "Админ-панель закрыта.")


@router.callback_query(F.data == "admin:stats")
async def admin_stats(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if not is_admin_callback(callback, settings):
        await callback.answer()
        return
    await callback.answer()
    await state.clear()
    if callback.message is None:
        return
    stats = await services.requests.get_stats(session)
    await _edit_panel_message(callback.message, _format_stats(stats), reply_markup=admin_stats_keyboard())


@router.callback_query(F.data.startswith("admin:list:"))
async def admin_request_list(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if not is_admin_callback(callback, settings):
        await callback.answer()
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Раздел устарел", show_alert=True)
        return
    try:
        view = AdminListView(parts[2])
        page = _parse_page(parts[3])
    except (TypeError, ValueError):
        await callback.answer("Некорректный раздел", show_alert=True)
        return
    await callback.answer()
    await _render_list(callback, session, services, settings, state, view, page)


@router.callback_query(F.data.startswith("admin:detail:"))
async def admin_request_detail(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if not is_admin_callback(callback, settings):
        await callback.answer()
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 5:
        await callback.answer("Заявка устарела", show_alert=True)
        return
    try:
        request_id = int(parts[2])
        view = AdminListView(parts[3])
        page = _parse_page(parts[4])
    except (TypeError, ValueError):
        await callback.answer("Некорректная заявка", show_alert=True)
        return
    request = await services.requests.get_by_id(session, request_id)
    if request is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    await callback.answer()
    events = await services.requests.get_events(session, request_id)
    keyboard = admin_request_keyboard(
        request.id,
        request.status,
        request.request_type,
        view=view,
        page=page,
    )
    if callback.message is not None:
        await _edit_panel_message(
            callback.message,
            format_request_details(request, events),
            reply_markup=keyboard,
        )


@router.callback_query(F.data.startswith("admin:confirm:"))
async def confirm_admin_status(
    callback: CallbackQuery,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if not is_admin_callback(callback, settings):
        await callback.answer()
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 6:
        await callback.answer("Действие устарело", show_alert=True)
        return
    try:
        request_id = int(parts[2])
        status = RequestStatus(parts[3])
        view = AdminListView(parts[4])
        page = _parse_page(parts[5])
    except (TypeError, ValueError):
        await callback.answer("Некорректное действие", show_alert=True)
        return
    if status not in {RequestStatus.DONE, RequestStatus.REJECTED}:
        await callback.answer("Это действие не требует подтверждения", show_alert=True)
        return
    request = await services.requests.get_by_id(session, request_id)
    if request is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    await callback.answer()
    if callback.message is not None:
        action = "подтвердить заявку" if status == RequestStatus.DONE else "отклонить заявку"
        await _edit_panel_message(
            callback.message,
            f"Вы действительно хотите {action}?\n\n{format_request_message(request)}",
            reply_markup=admin_status_confirmation_keyboard(
                request.id,
                status,
                view=view,
                page=page,
            ),
        )


@router.callback_query(F.data.startswith("admin:apply_status:"))
async def apply_admin_status(
    callback: CallbackQuery,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if not is_admin_callback(callback, settings):
        await callback.answer()
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 6:
        await callback.answer("Действие устарело", show_alert=True)
        return
    try:
        request_id = int(parts[2])
        status = RequestStatus(parts[3])
        view = AdminListView(parts[4])
        page = _parse_page(parts[5])
    except (TypeError, ValueError):
        await callback.answer("Некорректное действие", show_alert=True)
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
    if request.status != previous_status:
        await services.notifications.enqueue_client_status(session, request)
    await callback.answer(
        f"Статус: {status_label(request.status)}"
        if request.status != previous_status
        else f"Статус уже: {status_label(request.status)}"
    )
    events = await services.requests.get_events(session, request_id)
    keyboard = admin_request_keyboard(
        request.id,
        request.status,
        request.request_type,
        view=view,
        page=page,
    )
    if callback.message is not None:
        await _edit_panel_message(
            callback.message,
            format_request_details(request, events),
            reply_markup=keyboard,
        )
    logger.info("Admin panel updated request status: request_id=%s status=%s", request.id, request.status)


@router.callback_query(F.data.startswith("admin:reply:"))
async def start_panel_reply(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if not is_admin_callback(callback, settings):
        await callback.answer()
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 5:
        await callback.answer("Заявка устарела", show_alert=True)
        return
    try:
        request_id = int(parts[2])
        view = AdminListView(parts[3])
        page = _parse_page(parts[4])
    except (TypeError, ValueError):
        await callback.answer("Некорректная заявка", show_alert=True)
        return
    request = await services.requests.get_by_id(session, request_id)
    if request is None or request.user is None:
        await callback.answer("Заявка или клиент не найдены", show_alert=True)
        return
    if request.status in {
        RequestStatus.DONE.value,
        RequestStatus.REJECTED.value,
        RequestStatus.CANCELLED.value,
    }:
        await callback.answer("Заявка уже закрыта", show_alert=True)
        return
    await state.clear()
    panel_data = {
        "request_id": request_id,
        "panel_view": view.value,
        "panel_page": page,
    }
    if callback.message is not None:
        panel_data.update(
            panel_message_id=callback.message.message_id,
            panel_chat_id=callback.message.chat.id,
        )
    await state.update_data(**panel_data)
    await state.set_state(AdminStates.reply)
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(f"Напишите ответ клиенту по заявке #{request_id}. Для отмены: /cancel")


@router.callback_query(F.data == "admin:search")
async def start_admin_search(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
) -> None:
    if not is_admin_callback(callback, settings):
        await callback.answer()
        return
    await state.clear()
    if callback.message is not None:
        await state.update_data(
            panel_message_id=callback.message.message_id,
            panel_chat_id=callback.message.chat.id,
        )
    await state.set_state(AdminPanelStates.search)
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer("Введите имя, телефон или ID заявки. Для отмены: /cancel")


@router.message(AdminPanelStates.search, Command("cancel"))
async def cancel_admin_search(message: Message, state: FSMContext, settings: Settings) -> None:
    if not is_admin_message(message, settings):
        await state.clear()
        return
    await state.clear()
    await message.answer("Поиск отменён.")


@router.message(AdminPanelStates.search, F.text)
async def perform_admin_search(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if not is_admin_message(message, settings):
        await state.clear()
        return
    search_query = " ".join((message.text or "").strip().split())[:100]
    if len(search_query) < 2:
        await message.answer("Введите минимум 2 символа для поиска.")
        return

    await state.update_data(search_query=search_query)
    await state.set_state(AdminPanelStates.search_results)
    requests, _ = await _requests_for_view(
        session,
        services,
        settings,
        state,
        AdminListView.SEARCH,
        0,
    )
    has_next = len(requests) > ADMIN_PANEL_PAGE_SIZE
    visible_requests = requests[:ADMIN_PANEL_PAGE_SIZE]
    text = _format_request_list(
        AdminListView.SEARCH,
        visible_requests,
        page=0,
        has_next=has_next,
        search_query=search_query,
    )
    keyboard = admin_request_list_keyboard(
        [(request.id, request.customer_name) for request in visible_requests],
        view=AdminListView.SEARCH,
        page=0,
        has_next=has_next,
    )
    data = await state.get_data()
    panel_message_id = data.get("panel_message_id")
    panel_chat_id = data.get("panel_chat_id")
    if panel_message_id and panel_chat_id:
        try:
            await message.bot.edit_message_text(
                chat_id=int(panel_chat_id),
                message_id=int(panel_message_id),
                text=text,
                reply_markup=keyboard,
            )
            return
        except TelegramBadRequest:
            logger.warning("Could not edit admin panel after search", exc_info=True)
    await message.answer(text, reply_markup=keyboard)
