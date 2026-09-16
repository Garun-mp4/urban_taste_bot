import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.notifications import (
    AdminNotificationService,
    format_client_request_message,
    status_label,
)


def test_client_request_uses_human_readable_status():
    request = SimpleNamespace(
        id=7,
        request_type="reservation",
        reservation_date=None,
        reservation_time=None,
        guests=2,
        status="IN_PROGRESS",
    )

    assert "Статус: В работе" in format_client_request_message(request)


def test_unknown_status_is_preserved_for_diagnostics():
    assert status_label("CUSTOM_STATUS") == "CUSTOM_STATUS"


def test_client_reply_delivery_uses_persisted_message_text():
    async def run_check():
        bot = SimpleNamespace(send_message=AsyncMock())
        service = AdminNotificationService(bot, admin_chat_id=99)
        delivery = SimpleNamespace(
            delivery_type="client_reply:123",
            destination_chat_id=42,
            message_text="Ответ администратора",
        )

        await service.send_delivery(delivery)

        bot.send_message.assert_awaited_once_with(
            chat_id=42,
            text="Ответ администратора",
        )

    asyncio.run(run_check())
