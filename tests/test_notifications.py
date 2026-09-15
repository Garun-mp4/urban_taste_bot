from types import SimpleNamespace

from app.services.notifications import format_client_request_message, status_label


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
