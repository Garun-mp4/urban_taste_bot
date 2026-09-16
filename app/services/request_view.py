"""Plain-text views shared by the admin request interfaces."""

from app.database.models import ClientRequest, RequestEvent, RequestEventType
from app.services.notifications import format_request_message, status_label


def format_request_details(
    request: ClientRequest,
    events: list[RequestEvent],
    *,
    max_length: int = 3800,
) -> str:
    lines = [format_request_message(request)]
    if request.user is not None:
        lines.extend(("", f"Telegram ID клиента: {request.user.telegram_id}"))
    if events:
        lines.extend(("", "История заявки:"))
        event_labels = {
            RequestEventType.CREATED.value: "создана",
            RequestEventType.STATUS_CHANGED.value: "статус изменён",
            RequestEventType.CLIENT_CANCELLED.value: "отменена клиентом",
            RequestEventType.ADMIN_REPLY.value: "ответ поставлен в очередь клиенту",
        }
        for event in events:
            timestamp = event.created_at.strftime("%d.%m.%Y %H:%M")
            label = event_labels.get(event.event_type, event.event_type)
            if event.event_type == RequestEventType.STATUS_CHANGED.value:
                transition = (
                    f" ({status_label(event.from_status)} → {status_label(event.to_status)})"
                    if event.from_status and event.to_status
                    else ""
                )
                label += transition
            if event.note:
                label += f": {event.note[:500]}"
            lines.append(f"{timestamp} — {label}")
    details = "\n".join(lines)
    if len(details) <= max_length:
        return details
    return details[: max_length - 1].rstrip() + "…"
