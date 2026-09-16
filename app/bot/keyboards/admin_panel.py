from enum import StrEnum

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import RequestStatus, RequestType

ADMIN_PANEL_PAGE_SIZE = 5


class AdminListView(StrEnum):
    NEW = "new"
    TODAY = "today"
    QUESTIONS = "questions"
    ALL = "all"
    SEARCH = "search"


def admin_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🆕 Новые", callback_data="admin:list:new:0"),
                InlineKeyboardButton(text="📅 Сегодня", callback_data="admin:list:today:0"),
            ],
            [
                InlineKeyboardButton(text="💬 Вопросы", callback_data="admin:list:questions:0"),
                InlineKeyboardButton(text="📋 Все заявки", callback_data="admin:list:all:0"),
            ],
            [
                InlineKeyboardButton(text="🔍 Поиск", callback_data="admin:search"),
                InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats"),
            ],
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:home"),
                InlineKeyboardButton(text="✖️ Закрыть", callback_data="admin:close"),
            ],
        ]
    )


def admin_request_list_keyboard(
    request_ids: list[tuple[int, str]],
    *,
    view: AdminListView,
    page: int,
    has_next: bool,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"#{request_id} · {' '.join(str(customer_name).split())[:32]}",
                callback_data=f"admin:detail:{request_id}:{view.value}:{page}",
            )
        ]
        for request_id, customer_name in request_ids
    ]
    navigation: list[InlineKeyboardButton] = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="‹ Назад",
                callback_data=f"admin:list:{view.value}:{page - 1}",
            )
        )
    if has_next:
        navigation.append(
            InlineKeyboardButton(
                text="Дальше ›",
                callback_data=f"admin:list:{view.value}:{page + 1}",
            )
        )
    if navigation:
        rows.append(navigation)
    rows.append(
        [
            InlineKeyboardButton(text="🏠 Панель", callback_data="admin:home"),
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data=f"admin:list:{view.value}:{page}",
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_request_keyboard(
    request_id: int,
    status: str,
    request_type: str,
    *,
    view: AdminListView,
    page: int,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if status == RequestStatus.NEW.value:
        rows.append(
            [
                InlineKeyboardButton(
                    text="В работу",
                    callback_data=(
                        f"admin:apply_status:{request_id}:{RequestStatus.IN_PROGRESS.value}:"
                        f"{view.value}:{page}"
                    ),
                )
            ]
        )
    if status in {RequestStatus.NEW.value, RequestStatus.IN_PROGRESS.value}:
        action_text = "✅ Подтвердить" if request_type == RequestType.RESERVATION.value else "✅ Завершить"
        rows.extend(
            [
                [
                    InlineKeyboardButton(
                        text=action_text,
                        callback_data=(
                            f"admin:confirm:{request_id}:{RequestStatus.DONE.value}:{view.value}:{page}"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⛔ Отклонить",
                        callback_data=(
                            f"admin:confirm:{request_id}:{RequestStatus.REJECTED.value}:{view.value}:{page}"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="💬 Ответить клиенту",
                        callback_data=f"admin:reply:{request_id}:{view.value}:{page}",
                    )
                ],
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ К списку",
                callback_data=f"admin:list:{view.value}:{page}",
            ),
            InlineKeyboardButton(text="🏠 Панель", callback_data="admin:home"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_status_confirmation_keyboard(
    request_id: int,
    status: RequestStatus,
    *,
    view: AdminListView,
    page: int,
) -> InlineKeyboardMarkup:
    action_text = "подтверждение брони" if status == RequestStatus.DONE else "отклонение заявки"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅ Подтвердить {action_text}",
                    callback_data=(f"admin:apply_status:{request_id}:{status.value}:{view.value}:{page}"),
                )
            ],
            [
                InlineKeyboardButton(
                    text="↩️ Отмена",
                    callback_data=f"admin:detail:{request_id}:{view.value}:{page}",
                )
            ],
        ]
    )


def admin_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏠 Панель", callback_data="admin:home"),
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:stats"),
            ]
        ]
    )
