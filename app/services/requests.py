from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import (
    ClientRequest,
    NotificationDelivery,
    NotificationDeliveryStatus,
    RequestEvent,
    RequestEventType,
    RequestStatus,
    RequestType,
    User,
)
from app.services.availability import (
    available_time_slots,
    intervals_overlap,
)


@dataclass(frozen=True, slots=True)
class RequestStats:
    users_total: int
    requests_total: int
    new_requests: int
    in_progress_requests: int
    done_requests: int
    rejected_requests: int
    cancelled_requests: int
    pending_deliveries: int
    failed_deliveries: int


class ReservationSlotUnavailable(ValueError):
    """Raised when a requested reservation cannot be accepted."""


ACTIVE_RESERVATION_STATUSES = (
    RequestStatus.NEW.value,
    RequestStatus.IN_PROGRESS.value,
    RequestStatus.DONE.value,
)


class RequestService:
    def __init__(
        self,
        *,
        timezone: str = "Europe/Moscow",
        capacity: int = 50,
        max_guests: int = 50,
        duration_minutes: int = 90,
        slot_interval_minutes: int = 30,
        min_advance_minutes: int = 30,
        max_days: int = 30,
    ) -> None:
        self._timezone = timezone
        self._capacity = capacity
        self._max_guests = max_guests
        self._duration_minutes = duration_minutes
        self._slot_interval_minutes = slot_interval_minutes
        self._min_advance_minutes = min_advance_minutes
        self._max_days = max_days

    def validate_reservation_slot(
        self,
        *,
        reservation_date: date,
        reservation_time: time,
        guests: int,
    ) -> None:
        """Validate all booking invariants before touching the database."""

        if guests < 1 or guests > self._max_guests or guests > self._capacity:
            raise ReservationSlotUnavailable(
                f"Количество гостей должно быть от 1 до {self._max_guests}"
            )

        today = datetime.now(ZoneInfo(self._timezone)).date()
        if reservation_date < today:
            raise ReservationSlotUnavailable("Дата бронирования не может быть в прошлом")
        if reservation_date > today + timedelta(days=self._max_days):
            raise ReservationSlotUnavailable(
                f"Бронирование доступно максимум на {self._max_days} дней вперёд"
            )

        available_slots = available_time_slots(
            reservation_date,
            slot_interval_minutes=self._slot_interval_minutes,
            duration_minutes=self._duration_minutes,
            timezone=self._timezone,
            min_advance_minutes=self._min_advance_minutes,
        )
        if reservation_time not in available_slots:
            raise ReservationSlotUnavailable(
                "Выбранное время уже недоступно. Выберите другой слот."
            )

    async def create_reservation(
        self,
        session: AsyncSession,
        user: User,
        *,
        customer_name: str,
        phone: str,
        guests: int,
        reservation_date: date,
        reservation_time: time,
    ) -> ClientRequest:
        self.validate_reservation_slot(
            reservation_date=reservation_date,
            reservation_time=reservation_time,
            guests=guests,
        )

        # Serialize bookings for one calendar day so two concurrent clients cannot
        # both pass the availability check before either transaction commits.
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": reservation_date.toordinal()},
        )
        if not await self.is_slot_available(
            session,
            reservation_date=reservation_date,
            reservation_time=reservation_time,
            guests=guests,
        ):
            raise ReservationSlotUnavailable(
                "На выбранное время уже недостаточно свободных мест. Выберите другой слот."
            )
        if await self._has_user_reservation_conflict(
            session,
            user_id=user.id,
            reservation_date=reservation_date,
            reservation_time=reservation_time,
        ):
            raise ReservationSlotUnavailable(
                "У вас уже есть активная заявка на пересекающееся время."
            )

        request = ClientRequest(
            user=user,
            request_type=RequestType.RESERVATION.value,
            status=RequestStatus.NEW.value,
            customer_name=customer_name,
            phone=phone,
            guests=guests,
            reservation_date=reservation_date,
            reservation_time=reservation_time,
        )
        session.add(request)
        await session.flush()
        await self.add_event(
            session,
            request.id,
            event_type=RequestEventType.CREATED,
            to_status=request.status,
        )
        return request

    async def get_available_slots(
        self,
        session: AsyncSession,
        reservation_date: date,
        *,
        guests: int = 1,
    ) -> list[time]:
        candidates = available_time_slots(
            reservation_date,
            slot_interval_minutes=self._slot_interval_minutes,
            duration_minutes=self._duration_minutes,
            timezone=self._timezone,
            min_advance_minutes=self._min_advance_minutes,
        )
        available: list[time] = []
        for candidate in candidates:
            if await self.is_slot_available(
                session,
                reservation_date=reservation_date,
                reservation_time=candidate,
                guests=guests,
            ):
                available.append(candidate)
        return available

    async def is_slot_available(
        self,
        session: AsyncSession,
        *,
        reservation_date: date,
        reservation_time: time,
        guests: int,
    ) -> bool:
        try:
            self.validate_reservation_slot(
                reservation_date=reservation_date,
                reservation_time=reservation_time,
                guests=guests,
            )
        except ReservationSlotUnavailable:
            return False

        result = await session.execute(
            select(ClientRequest.reservation_time, ClientRequest.guests).where(
                ClientRequest.request_type == RequestType.RESERVATION.value,
                ClientRequest.status.in_(ACTIVE_RESERVATION_STATUSES),
                ClientRequest.reservation_date == reservation_date,
            )
        )
        occupied_guests = sum(
            int(existing_guests or 0)
            for existing_time, existing_guests in result.all()
            if existing_time is not None
            and intervals_overlap(
                reservation_time,
                existing_time,
                duration_minutes=self._duration_minutes,
            )
        )
        return occupied_guests + guests <= self._capacity

    async def _has_user_reservation_conflict(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        reservation_date: date,
        reservation_time: time,
    ) -> bool:
        result = await session.execute(
            select(ClientRequest.reservation_time).where(
                ClientRequest.user_id == user_id,
                ClientRequest.request_type == RequestType.RESERVATION.value,
                ClientRequest.status.in_(ACTIVE_RESERVATION_STATUSES),
                ClientRequest.reservation_date == reservation_date,
            )
        )
        return any(
            existing_time is not None
            and intervals_overlap(
                reservation_time,
                existing_time,
                duration_minutes=self._duration_minutes,
            )
            for (existing_time,) in result.all()
        )

    async def create_question(
        self,
        session: AsyncSession,
        user: User,
        *,
        question: str,
    ) -> ClientRequest:
        request = ClientRequest(
            user=user,
            request_type=RequestType.QUESTION.value,
            status=RequestStatus.NEW.value,
            customer_name=user.name or "Не указано",
            phone=user.phone,
            details=question.strip()[:10000],
        )
        session.add(request)
        await session.flush()
        await self.add_event(
            session,
            request.id,
            event_type=RequestEventType.CREATED,
            to_status=request.status,
        )
        return request

    async def get_stats(self, session: AsyncSession) -> RequestStats:
        users_total = int((await session.scalar(select(func.count(User.id)))) or 0)
        requests_total = int((await session.scalar(select(func.count(ClientRequest.id)))) or 0)
        status_rows = (
            await session.execute(
                select(ClientRequest.status, func.count(ClientRequest.id)).group_by(
                    ClientRequest.status
                )
            )
        ).all()
        status_counts = {status: int(count) for status, count in status_rows}
        delivery_rows = (
            await session.execute(
                select(NotificationDelivery.status, func.count(NotificationDelivery.id)).group_by(
                    NotificationDelivery.status
                )
            )
        ).all()
        delivery_counts = {status: int(count) for status, count in delivery_rows}
        return RequestStats(
            users_total=users_total,
            requests_total=requests_total,
            new_requests=status_counts.get(RequestStatus.NEW.value, 0),
            in_progress_requests=status_counts.get(RequestStatus.IN_PROGRESS.value, 0),
            done_requests=status_counts.get(RequestStatus.DONE.value, 0),
            rejected_requests=status_counts.get(RequestStatus.REJECTED.value, 0),
            cancelled_requests=status_counts.get(RequestStatus.CANCELLED.value, 0),
            pending_deliveries=sum(
                delivery_counts.get(status, 0)
                for status in (
                    NotificationDeliveryStatus.PENDING.value,
                    NotificationDeliveryStatus.PROCESSING.value,
                )
            ),
            failed_deliveries=delivery_counts.get(NotificationDeliveryStatus.FAILED.value, 0),
        )

    async def get_latest(
        self,
        session: AsyncSession,
        limit: int = 10,
        *,
        status: RequestStatus | str | None = None,
        search: str | None = None,
    ) -> list[ClientRequest]:
        statement = (
            select(ClientRequest)
            .options(selectinload(ClientRequest.user))
            .order_by(desc(ClientRequest.created_at), desc(ClientRequest.id))
            .limit(limit)
        )
        if status is not None:
            status_value = status.value if isinstance(status, RequestStatus) else status
            statement = statement.where(ClientRequest.status == status_value)
        if search:
            search_pattern = f"%{search.strip()[:100]}%"
            statement = statement.where(
                ClientRequest.customer_name.ilike(search_pattern)
                | ClientRequest.phone.ilike(search_pattern)
                | ClientRequest.details.ilike(search_pattern)
            )
        result = await session.execute(statement)
        return list(result.scalars().all())

    async def get_by_id(self, session: AsyncSession, request_id: int) -> ClientRequest | None:
        result = await session.execute(
            select(ClientRequest)
            .options(selectinload(ClientRequest.user))
            .where(ClientRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def get_for_user(
        self,
        session: AsyncSession,
        user_id: int,
        limit: int = 10,
    ) -> list[ClientRequest]:
        result = await session.execute(
            select(ClientRequest)
            .where(ClientRequest.user_id == user_id)
            .order_by(desc(ClientRequest.created_at), desc(ClientRequest.id))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_events(
        self,
        session: AsyncSession,
        request_id: int,
        limit: int = 20,
    ) -> list[RequestEvent]:
        result = await session.execute(
            select(RequestEvent)
            .where(RequestEvent.request_id == request_id)
            .order_by(RequestEvent.created_at, RequestEvent.id)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def add_event(
        self,
        session: AsyncSession,
        request_id: int,
        *,
        event_type: RequestEventType | str,
        from_status: str | None = None,
        to_status: str | None = None,
        actor_telegram_id: int | None = None,
        note: str | None = None,
    ) -> RequestEvent:
        event = RequestEvent(
            request_id=request_id,
            event_type=event_type.value if isinstance(event_type, RequestEventType) else event_type,
            from_status=from_status,
            to_status=to_status,
            actor_telegram_id=actor_telegram_id,
            note=note.strip()[:4000] if note else None,
        )
        session.add(event)
        await session.flush()
        return event

    async def update_status(
        self,
        session: AsyncSession,
        request_id: int,
        status: RequestStatus,
        *,
        actor_telegram_id: int | None = None,
        note: str | None = None,
    ) -> ClientRequest | None:
        result = await session.execute(
            select(ClientRequest)
            .options(selectinload(ClientRequest.user))
            .where(ClientRequest.id == request_id)
            .with_for_update()
        )
        request = result.scalar_one_or_none()
        if request is None:
            return None
        if request.status == status.value:
            return request
        allowed_transitions = {
            RequestStatus.NEW.value: {
                RequestStatus.IN_PROGRESS.value,
                RequestStatus.DONE.value,
                RequestStatus.REJECTED.value,
            },
            RequestStatus.IN_PROGRESS.value: {
                RequestStatus.DONE.value,
                RequestStatus.REJECTED.value,
            },
            RequestStatus.DONE.value: set(),
            RequestStatus.REJECTED.value: set(),
            RequestStatus.CANCELLED.value: set(),
        }
        if status.value not in allowed_transitions.get(request.status, set()):
            raise ValueError(f"Нельзя изменить статус {request.status} на {status.value}")
        previous_status = request.status
        request.status = status.value
        await session.flush()
        await self.add_event(
            session,
            request.id,
            event_type=RequestEventType.STATUS_CHANGED,
            from_status=previous_status,
            to_status=request.status,
            actor_telegram_id=actor_telegram_id,
            note=note,
        )
        return request

    async def cancel_for_user(
        self,
        session: AsyncSession,
        user_id: int,
        request_id: int,
    ) -> ClientRequest | None:
        result = await session.execute(
            select(ClientRequest)
            .options(selectinload(ClientRequest.user))
            .where(ClientRequest.id == request_id, ClientRequest.user_id == user_id)
            .with_for_update()
        )
        request = result.scalar_one_or_none()
        if request is None:
            return None
        if request.status not in {
            RequestStatus.NEW.value,
            RequestStatus.IN_PROGRESS.value,
        }:
            raise ValueError("Эту заявку уже нельзя отменить")
        previous_status = request.status
        request.status = RequestStatus.CANCELLED.value
        await session.flush()
        await self.add_event(
            session,
            request.id,
            event_type=RequestEventType.CLIENT_CANCELLED,
            from_status=previous_status,
            to_status=request.status,
            actor_telegram_id=user_id,
        )
        return request
