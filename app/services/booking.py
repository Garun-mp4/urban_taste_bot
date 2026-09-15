import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


class BookingValidationError(ValueError):
    """Raised when a booking form field is invalid."""


def validate_customer_name(value: str) -> str:
    name = " ".join(value.strip().split())
    if len(name) < 2:
        raise BookingValidationError("Имя должно содержать минимум 2 символа")
    if len(name) > 100:
        raise BookingValidationError("Имя слишком длинное")
    return name


def parse_guests(value: str) -> int:
    raw_value = value.strip()
    if not raw_value.isdigit():
        raise BookingValidationError("Введите количество гостей целым числом от 1 до 50")
    guests = int(raw_value)
    if not 1 <= guests <= 50:
        raise BookingValidationError("Количество гостей должно быть от 1 до 50")
    return guests


def parse_reservation_date(value: str, timezone: str) -> date:
    normalized = value.strip().lower()
    today = datetime.now(ZoneInfo(timezone)).date()
    if normalized in {"сегодня", "today"}:
        return today
    if normalized in {"завтра", "tomorrow"}:
        return today + timedelta(days=1)

    for pattern in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(normalized, pattern).date()
        except ValueError:
            continue
        if parsed < today:
            raise BookingValidationError("Дата бронирования не может быть в прошлом")
        return parsed
    raise BookingValidationError("Введите дату в формате ДД.ММ.ГГГГ или напишите «сегодня»")


def parse_reservation_time(value: str) -> time:
    normalized = value.strip().replace(".", ":")
    for pattern in ("%H:%M", "%H%M"):
        try:
            return datetime.strptime(normalized, pattern).time()
        except ValueError:
            continue
    raise BookingValidationError("Введите время в формате ЧЧ:ММ, например 19:30")


def normalize_phone(value: str) -> str:
    phone = " ".join(value.strip().split())
    digits = re.sub(r"\D", "", phone)
    if not 7 <= len(digits) <= 15:
        raise BookingValidationError("Введите корректный номер телефона")
    if phone.startswith("+"):
        normalized = "+" + digits
    elif digits.startswith("8") and len(digits) == 11:
        normalized = "+7" + digits[1:]
    elif digits.startswith("7") and len(digits) == 11:
        normalized = "+" + digits
    else:
        normalized = "+" + digits
    return normalized
