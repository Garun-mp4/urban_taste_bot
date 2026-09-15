from dataclasses import dataclass
from datetime import date, time

from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import ClientRequest, RequestStatus, RequestType, User
from app.services.availability import (
    available_time_slots,
    intervals_overlap,
    reservation_window,
)


@dataclass(frozen=True, slots=True)
class RequestStats:
    users_total: int
    requests_total: int
    new_requests: int


class ReservationSlotUnavailable(ValueError):
    """Raised when a requested reservation cannot be accepted."""


class RequestService:
    def __init__(
        self,
        *,
        timezone: str = "Europe/Moscow",
        capacity: int = 50,
        duration_minutes: int = 90,
        slot_interval_minutes: int = 30,
        min_advance_minutes: int = 30,
    ) -> None:
        self._timezone = timezone
        self._capacity = capacity
        self._duration_minutes = duration_minutes
        self._slot_interval_minutes = slot_interval_minutes
        self._min_advance_minutes = min_advance_minutes

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
        if reservation_window(
            reservation_date,
            reservation_time,
            duration_minutes=self._duration_minutes,
        ) is None:
            raise ReservationSlotUnavailable("Ресторан закрыт в выбранное время")

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
        if guests < 1 or guests > self._capacity:
            return False
        if reservation_window(
            reservation_date,
            reservation_time,
            duration_minutes=self._duration_minutes,
        ) is None:
            return False

        result = await session.execute(
            select(ClientRequest.reservation_time, ClientRequest.guests).where(
                ClientRequest.request_type == RequestType.RESERVATION.value,
                ClientRequest.status.in_(
                    [
                        RequestStatus.NEW.value,
                        RequestStatus.IN_PROGRESS.value,
                        RequestStatus.DONE.value,
                    ]
                ),
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
        return request

    async def get_stats(self, session: AsyncSession) -> RequestStats:
        users_total = int((await session.scalar(select(func.count(User.id)))) or 0)
        requests_total = int((await session.scalar(select(func.count(ClientRequest.id)))) or 0)
        new_requests = int(
            (
                await session.scalar(
                    select(func.count(ClientRequest.id)).where(
                        ClientRequest.status == RequestStatus.NEW.value
                    )
                )
            )
            or 0
        )
        return RequestStats(
            users_total=users_total,
            requests_total=requests_total,
            new_requests=new_requests,
        )

    async def get_latest(
        self,
        session: AsyncSession,
        limit: int = 10,
        *,
        status: RequestStatus | str | None = None,
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

    async def update_status(
        self,
        session: AsyncSession,
        request_id: int,
        status: RequestStatus,
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
        request.status = status.value
        await session.flush()
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
        request.status = RequestStatus.CANCELLED.value
        await session.flush()
        return request
