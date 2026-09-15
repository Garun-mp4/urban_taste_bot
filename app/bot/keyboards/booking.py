import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def booking_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить", callback_data="booking:cancel")],
        ]
    )


def guests_keyboard(max_guests: int = 50) -> InlineKeyboardMarkup:
    max_guests = max(1, max_guests)
    buttons = [
        InlineKeyboardButton(text=str(guests), callback_data=f"booking:guests:{guests}")
        for guests in range(1, min(max_guests, 6) + 1)
    ]
    rows = [buttons[index : index + 3] for index in range(0, len(buttons), 3)]
    if max_guests > 6:
        rows.append(
            [InlineKeyboardButton(text="Другое число", callback_data="booking:guests:custom")]
        )
    rows.append([InlineKeyboardButton(text="❌ Отменить", callback_data="booking:cancel")])
    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def custom_guests_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="booking:back:guests")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="booking:cancel")],
        ]
    )


def booking_calendar_keyboard(
    *,
    timezone: str,
    reference: date | None = None,
    max_days: int = 30,
) -> InlineKeyboardMarkup:
    today = datetime.now(ZoneInfo(timezone)).date()
    last_day = today + timedelta(days=max_days)
    reference = reference or today
    month_grid = calendar.monthcalendar(reference.year, reference.month)
    month_name = f"{reference.month:02d}.{reference.year}"
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=f"Выберите дату · {month_name}", callback_data="booking:noop")],
        [
            InlineKeyboardButton(text=weekday, callback_data="booking:noop")
            for weekday in ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
        ],
    ]
    for week in month_grid:
        row: list[InlineKeyboardButton] = []
        for day_number in week:
            if day_number == 0:
                row.append(InlineKeyboardButton(text="·", callback_data="booking:noop"))
                continue
            selected = date(reference.year, reference.month, day_number)
            if today <= selected <= last_day:
                row.append(
                    InlineKeyboardButton(
                        text=str(day_number),
                        callback_data=f"booking:date:{selected.isoformat()}",
                    )
                )
            else:
                row.append(InlineKeyboardButton(text="·", callback_data="booking:noop"))
        rows.append(row)

    navigation: list[InlineKeyboardButton] = []
    previous_month = (reference.replace(day=1) - timedelta(days=1)).replace(day=1)
    next_month = (reference.replace(day=28) + timedelta(days=4)).replace(day=1)
    if previous_month >= today.replace(day=1):
        navigation.append(
            InlineKeyboardButton(
                text="‹ Предыдущий",
                callback_data=f"booking:month:{previous_month.isoformat()}",
            )
        )
    if next_month <= last_day.replace(day=1):
        navigation.append(
            InlineKeyboardButton(
                text="Следующий ›",
                callback_data=f"booking:month:{next_month.isoformat()}",
            )
        )
    if navigation:
        rows.append(navigation)
    rows.append([InlineKeyboardButton(text="❌ Отменить", callback_data="booking:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def time_slots_keyboard(slots: list[str]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=slot, callback_data=f"booking:time:{slot.replace(':', '')}")
        for slot in slots
    ]
    rows = [buttons[index : index + 3] for index in range(0, len(buttons), 3)]
    rows.append([InlineKeyboardButton(text="⬅️ К календарю", callback_data="booking:back:date")])
    rows.append([InlineKeyboardButton(text="❌ Отменить", callback_data="booking:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def booking_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить заявку", callback_data="booking:confirm")],
            [InlineKeyboardButton(text="⬅️ Изменить данные", callback_data="booking:back:phone")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="booking:cancel")],
        ]
    )
