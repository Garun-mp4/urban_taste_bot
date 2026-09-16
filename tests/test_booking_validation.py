from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.services.availability import available_time_slots, intervals_overlap, reservation_window
from app.services.booking import (
    BookingValidationError,
    normalize_phone,
    parse_guests,
    parse_reservation_date,
    parse_reservation_time,
    validate_customer_name,
)
from app.services.requests import RequestService, ReservationSlotUnavailable


def test_customer_name_is_normalized():
    assert validate_customer_name("  Анна   Петрова ") == "Анна Петрова"


@pytest.mark.parametrize("value", ["", "0", "51", "три"])
def test_invalid_guest_count_is_rejected(value: str):
    with pytest.raises(BookingValidationError):
        parse_guests(value)


def test_guest_count_respects_configured_capacity():
    with pytest.raises(BookingValidationError, match="1 до 4"):
        parse_guests("5", max_guests=4)


def test_reservation_date_accepts_tomorrow():
    parsed = parse_reservation_date("завтра", "Europe/Moscow")
    assert parsed >= date.today()


def test_reservation_date_rejects_past():
    with pytest.raises(BookingValidationError, match="прошлом"):
        parse_reservation_date("01.01.2020", "Europe/Moscow")


@pytest.mark.parametrize("value", ["19:30", "19.30", "1930"])
def test_reservation_time_accepts_common_formats(value: str):
    assert parse_reservation_time(value).strftime("%H:%M") == "19:30"


def test_phone_is_normalized_to_international_format():
    assert normalize_phone("8 (900) 123-45-67") == "+79001234567"


def test_invalid_phone_is_rejected():
    with pytest.raises(BookingValidationError):
        normalize_phone("123")


def test_weekday_slots_end_before_closing_time():
    slots = available_time_slots(
        date(2026, 9, 17),
        slot_interval_minutes=30,
        duration_minutes=90,
        timezone="Europe/Moscow",
        now=datetime(2026, 9, 16, 8, 0, tzinfo=UTC),
    )

    assert slots[0] == time(10, 0)
    assert slots[-1] == time(21, 30)
    assert time(22, 0) not in slots


def test_weekend_midnight_closing_is_supported():
    window = reservation_window(date(2026, 9, 19), time(22, 30), duration_minutes=90)

    assert window is not None
    assert window[1].date() == date(2026, 9, 20)
    assert window[1].time() == time(0, 0)


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        (time(19, 0), time(20, 0), True),
        (time(19, 0), time(20, 30), False),
    ],
)
def test_reservation_intervals_are_compared_by_overlap(first, second, expected):
    assert intervals_overlap(first, second, duration_minutes=90) is expected


def test_request_service_rejects_misaligned_time_slot():
    service = RequestService()
    tomorrow = datetime.now(ZoneInfo("Europe/Moscow")).date() + timedelta(days=1)

    with pytest.raises(ReservationSlotUnavailable, match="недоступно"):
        service.validate_reservation_slot(
            reservation_date=tomorrow,
            reservation_time=time(19, 15),
            guests=2,
        )


def test_request_service_rejects_date_outside_booking_horizon():
    service = RequestService(max_days=7)
    future = datetime.now(ZoneInfo("Europe/Moscow")).date() + timedelta(days=8)

    with pytest.raises(ReservationSlotUnavailable, match="максимум на 7"):
        service.validate_reservation_slot(
            reservation_date=future,
            reservation_time=time(19, 0),
            guests=2,
        )
