from datetime import date, datetime, time
from types import SimpleNamespace

from app.bot.admin_access import is_admin_callback, is_admin_message
from app.bot.keyboards.admin_panel import (
    AdminListView,
    admin_home_keyboard,
    admin_request_keyboard,
)
from app.config import Settings
from app.database.models import RequestStatus, RequestType
from app.services.request_view import format_request_details


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "TELEGRAM_BOT_TOKEN": "test-token",
        "ADMIN_CHAT_ID": 42,
        "OPENAI_API_KEY": "test-key",
    }
    values.update(overrides)
    return Settings(**values)


def test_admin_message_guard_requires_configured_chat_and_actor():
    settings = _settings(ADMIN_USER_IDS="101,202")
    allowed = SimpleNamespace(
        chat=SimpleNamespace(id=42, type="supergroup"),
        from_user=SimpleNamespace(id=101),
    )
    wrong_chat = SimpleNamespace(
        chat=SimpleNamespace(id=99, type="private"),
        from_user=SimpleNamespace(id=99),
    )
    wrong_actor = SimpleNamespace(
        chat=SimpleNamespace(id=42, type="supergroup"),
        from_user=SimpleNamespace(id=303),
    )

    assert is_admin_message(allowed, settings)
    assert not is_admin_message(wrong_chat, settings)
    assert not is_admin_message(wrong_actor, settings)


def test_admin_callback_guard_rejects_callback_without_admin_message():
    settings = _settings()
    callback = SimpleNamespace(message=None, from_user=SimpleNamespace(id=42))

    assert not is_admin_callback(callback, settings)


def test_admin_home_keyboard_exposes_action_first_sections():
    callback_data = {button.callback_data for row in admin_home_keyboard().inline_keyboard for button in row}

    assert "admin:list:new:0" in callback_data
    assert "admin:list:today:0" in callback_data
    assert "admin:list:questions:0" in callback_data
    assert "admin:search" in callback_data
    assert "admin:stats" in callback_data


def test_admin_request_keyboard_requires_confirmation_for_closing_request():
    keyboard = admin_request_keyboard(
        7,
        RequestStatus.IN_PROGRESS.value,
        RequestType.RESERVATION.value,
        view=AdminListView.TODAY,
        page=2,
    )
    callback_data = {button.callback_data for row in keyboard.inline_keyboard for button in row}

    assert "admin:confirm:7:DONE:today:2" in callback_data
    assert "admin:confirm:7:REJECTED:today:2" in callback_data
    assert "admin:reply:7:today:2" in callback_data


def test_request_details_are_bounded_and_include_audit_history():
    request = SimpleNamespace(
        id=7,
        request_type=RequestType.QUESTION.value,
        customer_name="Гарун",
        phone="+79990000000",
        details="Какой у вас график работы?",
        status=RequestStatus.IN_PROGRESS.value,
        reservation_date=None,
        reservation_time=None,
        guests=None,
        user=SimpleNamespace(telegram_id=42),
    )
    events = [
        SimpleNamespace(
            event_type="STATUS_CHANGED",
            from_status=RequestStatus.NEW.value,
            to_status=RequestStatus.IN_PROGRESS.value,
            note="Взято в работу",
            created_at=datetime(2026, 9, 16, 1, 40),
        )
    ]

    details = format_request_details(request, events, max_length=3800)

    assert len(details) <= 3800
    assert "Telegram ID клиента: 42" in details
    assert "В работе" in details
    assert "Взято в работу" in details


def test_request_details_truncate_long_audit_note():
    request = SimpleNamespace(
        id=8,
        request_type=RequestType.RESERVATION.value,
        customer_name="Гарун",
        phone=None,
        details=None,
        status=RequestStatus.NEW.value,
        reservation_date=date(2026, 9, 20),
        reservation_time=time(19, 0),
        guests=4,
        user=None,
    )
    events = [
        SimpleNamespace(
            event_type="CREATED",
            from_status=None,
            to_status=None,
            note="x" * 5000,
            created_at=datetime(2026, 9, 16, 1, 40),
        )
    ]

    details = format_request_details(request, events)

    assert len(details) <= 3800
    assert "x" * 5000 not in details
