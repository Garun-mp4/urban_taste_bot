import asyncio
import logging
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.bot.keyboards.admin import request_actions_keyboard
from app.database.models import (
    ClientRequest,
    NotificationDelivery,
    NotificationDeliveryStatus,
    RequestType,
)

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "NEW": "Новая",
    "IN_PROGRESS": "В работе",
    "DONE": "Завершена",
    "REJECTED": "Отклонена",
    "CANCELLED": "Отменена",
}


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def format_request_message(request: ClientRequest) -> str:
    if request.request_type == RequestType.RESERVATION.value:
        reservation_date = (
            request.reservation_date.strftime("%d.%m.%Y") if request.reservation_date else "не указана"
        )
        reservation_time = (
            request.reservation_time.strftime("%H:%M") if request.reservation_time else "не указано"
        )
        return (
            "Новая заявка на бронирование\n\n"
            f"ID: {request.id}\n"
            f"Клиент: {request.customer_name}\n"
            f"Телефон: {request.phone or 'не указан'}\n"
            f"Дата: {reservation_date} {reservation_time}\n"
            f"Количество гостей: {request.guests or 'не указано'}\n"
            f"Статус: {request.status}"
        )

    return (
        "Новое обращение клиента\n\n"
        f"ID: {request.id}\n"
        f"Клиент: {request.customer_name}\n"
        f"Телефон: {request.phone or 'не указан'}\n"
        f"Вопрос: {(request.details or 'не указан')[:2500]}\n"
        f"Статус: {request.status}"
    )


def format_admin_update_message(request: ClientRequest) -> str:
    return "Обновление заявки клиента\n\n" + format_request_message(request)


def format_client_request_message(request: ClientRequest) -> str:
    if request.request_type == RequestType.RESERVATION.value:
        reservation_date = (
            request.reservation_date.strftime("%d.%m.%Y") if request.reservation_date else "не указана"
        )
        reservation_time = (
            request.reservation_time.strftime("%H:%M") if request.reservation_time else "не указано"
        )
        return (
            "Заявка на бронирование\n\n"
            f"Дата: {reservation_date}\n"
            f"Время: {reservation_time}\n"
            f"Гостей: {request.guests or 'не указано'}\n"
            f"Статус: {status_label(request.status)}"
        )
    return (
        f"Обращение #{request.id}\n"
        f"Статус: {status_label(request.status)}\n"
        f"Вопрос: {request.details or 'не указан'}"
    )


class AdminNotificationService:
    def __init__(self, bot: Bot, admin_chat_id: int) -> None:
        self._bot = bot
        self._admin_chat_id = admin_chat_id

    async def enqueue_request(self, session: AsyncSession, request: ClientRequest) -> None:
        """Persist an admin notification in the same transaction as its request."""

        await self._enqueue_delivery(
            session,
            request_id=request.id,
            destination_chat_id=self._admin_chat_id,
            delivery_type="admin_request",
        )

    @staticmethod
    async def _enqueue_delivery(
        session: AsyncSession,
        *,
        request_id: int,
        destination_chat_id: int,
        delivery_type: str,
    ) -> None:
        statement = pg_insert(NotificationDelivery).values(
            request_id=request_id,
            destination_chat_id=destination_chat_id,
            delivery_type=delivery_type,
        )
        await session.execute(
            statement.on_conflict_do_nothing(
                index_elements=[
                    NotificationDelivery.request_id,
                    NotificationDelivery.destination_chat_id,
                    NotificationDelivery.delivery_type,
                ]
            )
        )

    async def send_delivery(self, delivery: NotificationDelivery) -> None:
        if delivery.delivery_type.startswith("client_status:"):
            await self._bot.send_message(
                chat_id=delivery.destination_chat_id,
                text=format_client_status_message(delivery.request),
            )
            return
        if delivery.delivery_type.startswith("admin_update:"):
            keyboard = request_actions_keyboard(
                delivery.request.id,
                delivery.request.status,
                delivery.request.request_type,
            )
            await self._bot.send_message(
                chat_id=delivery.destination_chat_id,
                text=format_admin_update_message(delivery.request),
                reply_markup=keyboard if keyboard.inline_keyboard else None,
            )
            return
        keyboard = request_actions_keyboard(
            delivery.request.id,
            delivery.request.status,
            delivery.request.request_type,
        )
        await self._bot.send_message(
            chat_id=delivery.destination_chat_id,
            text=format_request_message(delivery.request),
            reply_markup=keyboard if keyboard.inline_keyboard else None,
        )

    async def enqueue_client_status(self, session: AsyncSession, request: ClientRequest) -> None:
        if request.user is None:
            return
        await self._enqueue_delivery(
            session,
            request_id=request.id,
            destination_chat_id=request.user.telegram_id,
            delivery_type=f"client_status:{request.status}",
        )

    async def enqueue_admin_update(self, session: AsyncSession, request: ClientRequest) -> None:
        await self._enqueue_delivery(
            session,
            request_id=request.id,
            destination_chat_id=self._admin_chat_id,
            delivery_type=f"admin_update:{request.status}",
        )

    async def send_client_message(self, request: ClientRequest, text: str) -> None:
        if request.user is None:
            raise ValueError("Request has no linked user")
        await self._bot.send_message(chat_id=request.user.telegram_id, text=text)


def format_client_status_message(request: ClientRequest) -> str:
    if request.request_type == RequestType.RESERVATION.value:
        reservation_date = (
            request.reservation_date.strftime("%d.%m.%Y") if request.reservation_date else "не указана"
        )
        reservation_time = (
            request.reservation_time.strftime("%H:%M") if request.reservation_time else "не указано"
        )
        if request.status == "DONE":
            return (
                "✅ Бронирование подтверждено.\n\n"
                f"Дата: {reservation_date}\n"
                f"Время: {reservation_time}\n"
                f"Гостей: {request.guests or 'не указано'}"
            )
        if request.status == "REJECTED":
            return (
                "К сожалению, администратор не смог подтвердить это бронирование. "
                "Напишите нам, чтобы выбрать другой вариант."
            )
        if request.status == "CANCELLED":
            return (
                "Бронирование отменено. Если захотите выбрать другое время, "
                "я помогу оформить новую заявку."
            )
        return f"Статус вашей заявки на бронирование изменён: {status_label(request.status)}."
    if request.status == "DONE":
        return "✅ Ваше обращение обработано. Если появятся новые вопросы, напишите нам."
    if request.status == "REJECTED":
        return "Администратор не смог обработать обращение. Попробуйте уточнить вопрос другим сообщением."
    return f"Статус вашего обращения изменён: {status_label(request.status)}."


class NotificationWorker:
    """Deliver persisted notifications with retry and exponential backoff."""

    def __init__(
        self,
        notifications: AdminNotificationService,
        session_factory: async_sessionmaker[AsyncSession],
        poll_seconds: float,
        max_attempts: int,
    ) -> None:
        self._notifications = notifications
        self._session_factory = session_factory
        self._poll_seconds = poll_seconds
        self._max_attempts = max_attempts

    async def run(self) -> None:
        while True:
            try:
                processed = await self._process_one()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Notification worker iteration failed")
                processed = False

            if not processed:
                await asyncio.sleep(self._poll_seconds)

    async def _process_one(self) -> bool:
        async with self._session_factory() as session:
            result = await session.execute(
                select(NotificationDelivery)
                .options(
                    selectinload(NotificationDelivery.request).selectinload(ClientRequest.user)
                )
                .where(
                    or_(
                        and_(
                            NotificationDelivery.status.in_(
                                [
                                    NotificationDeliveryStatus.PENDING.value,
                                    NotificationDeliveryStatus.FAILED.value,
                                ]
                            ),
                            NotificationDelivery.attempts < self._max_attempts,
                            NotificationDelivery.next_attempt_at <= func.now(),
                        ),
                        and_(
                            NotificationDelivery.status == NotificationDeliveryStatus.PROCESSING.value,
                            NotificationDelivery.next_attempt_at <= func.now(),
                        ),
                    )
                )
                .order_by(NotificationDelivery.created_at, NotificationDelivery.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            delivery = result.scalar_one_or_none()
            if delivery is None:
                return False

            if (
                delivery.status == NotificationDeliveryStatus.PROCESSING.value
                and delivery.attempts >= self._max_attempts
            ):
                delivery.status = NotificationDeliveryStatus.FAILED.value
                delivery.last_error = "ProcessingLeaseExpired"
                await session.commit()
                logger.error(
                    "Notification delivery exhausted after a worker restart: delivery_id=%s request_id=%s",
                    delivery.id,
                    delivery.request_id,
                )
                return True

            delivery.status = NotificationDeliveryStatus.PROCESSING.value
            delivery.attempts += 1
            delivery.next_attempt_at = datetime.now(UTC) + timedelta(minutes=5)
            await session.flush()

            try:
                await self._notifications.send_delivery(delivery)
            except Exception as exc:
                delivery.status = NotificationDeliveryStatus.FAILED.value
                delivery.last_error = type(exc).__name__
                delay_seconds = min(2 ** delivery.attempts, 300)
                delivery.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
                await session.commit()
                logger.exception(
                    "Notification delivery failed: delivery_id=%s request_id=%s attempt=%s",
                    delivery.id,
                    delivery.request_id,
                    delivery.attempts,
                )
                return True

            delivery.status = NotificationDeliveryStatus.SENT.value
            delivery.sent_at = datetime.now(UTC)
            await session.commit()
            logger.info("Notification sent: delivery_id=%s request_id=%s", delivery.id, delivery.request_id)
            return True
