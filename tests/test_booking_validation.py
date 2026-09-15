from datetime import date

import pytest

from app.services.booking import (
    BookingValidationError,
    normalize_phone,
    parse_guests,
    parse_reservation_date,
    parse_reservation_time,
    validate_customer_name,
)


def test_customer_name_is_normalized():
    assert validate_customer_name("  Анна   Петрова ") == "Анна Петрова"


@pytest.mark.parametrize("value", ["", "0", "51", "три"])
def test_invalid_guest_count_is_rejected(value: str):
    with pytest.raises(BookingValidationError):
        parse_guests(value)


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
