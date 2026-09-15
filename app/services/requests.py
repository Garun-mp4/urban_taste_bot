from dataclasses import dataclass
from datetime import date, time

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import ClientRequest, RequestStatus, RequestType, User


@dataclass(frozen=True, slots=True)
class RequestStats:
    users_total: int
    requests_total: int
    new_requests: int


class RequestService:
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

    async def get_latest(self, session: AsyncSession, limit: int = 10) -> list[ClientRequest]:
        result = await session.execute(
            select(ClientRequest)
            .options(selectinload(ClientRequest.user))
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
        )
        request = result.scalar_one_or_none()
        if request is None:
            return None
        request.status = status.value
        await session.flush()
        return request
