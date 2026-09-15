from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

OPENING_HOURS: dict[int, tuple[time, time]] = {
    0: (time(10, 0), time(23, 0)),
    1: (time(10, 0), time(23, 0)),
    2: (time(10, 0), time(23, 0)),
    3: (time(10, 0), time(23, 0)),
    4: (time(10, 0), time(23, 0)),
    5: (time(11, 0), time(0, 0)),
    6: (time(11, 0), time(0, 0)),
}


def opening_hours(day: date) -> tuple[time, time]:
    return OPENING_HOURS[day.weekday()]


def reservation_window(
    day: date,
    start: time,
    *,
    duration_minutes: int,
) -> tuple[datetime, datetime] | None:
    """Return the local reservation interval when it fits the opening hours."""

    opening, closing = opening_hours(day)
    start_dt = datetime.combine(day, start)
    opening_dt = datetime.combine(day, opening)
    closing_day = day + timedelta(days=1) if closing <= opening else day
    closing_dt = datetime.combine(closing_day, closing)
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    if start_dt < opening_dt or end_dt > closing_dt:
        return None
    return start_dt, end_dt


def available_time_slots(
    day: date,
    *,
    slot_interval_minutes: int,
    duration_minutes: int,
    timezone: str,
    now: datetime | None = None,
    min_advance_minutes: int = 30,
) -> list[time]:
    """Generate bookable slots inside the restaurant's opening interval."""

    opening, _ = opening_hours(day)
    current = now or datetime.now(UTC)
    local_now = current.astimezone(ZoneInfo(timezone))
    cursor = datetime.combine(day, opening)
    if day == local_now.date():
        earliest = local_now.replace(tzinfo=None) + timedelta(minutes=min_advance_minutes)
        if earliest > cursor:
            cursor = earliest.replace(second=0, microsecond=0)
            remainder = cursor.minute % slot_interval_minutes
            if remainder:
                cursor += timedelta(minutes=slot_interval_minutes - remainder)

    slots: list[time] = []
    while cursor.date() == day:
        candidate = cursor.time().replace(second=0, microsecond=0)
        if reservation_window(day, candidate, duration_minutes=duration_minutes) is None:
            break
        slots.append(candidate)
        cursor += timedelta(minutes=slot_interval_minutes)
    return slots


def intervals_overlap(
    first_start: time,
    second_start: time,
    *,
    duration_minutes: int,
) -> bool:
    first_start_minutes = first_start.hour * 60 + first_start.minute
    second_start_minutes = second_start.hour * 60 + second_start.minute
    first_end_minutes = first_start_minutes + duration_minutes
    second_end_minutes = second_start_minutes + duration_minutes
    return first_start_minutes < second_end_minutes and second_start_minutes < first_end_minutes
