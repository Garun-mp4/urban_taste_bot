import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models import ProcessedEvent
from app.services.users import UserService

logger = logging.getLogger(__name__)


def event_key(event: Any) -> str | None:
    """Build a stable key for a Telegram event that may be delivered twice."""

    if isinstance(event, Message):
        return f"message:{event.chat.id}:{event.message_id}"
    if isinstance(event, CallbackQuery):
        return f"callback:{event.id}"
    return None


class DatabaseSessionMiddleware(BaseMiddleware):
    """Give every message/callback handler one transaction-scoped session."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        users: UserService,
        event_retention_days: int = 30,
        cleanup_interval: int = 1000,
    ) -> None:
        self._session_factory = session_factory
        self._users = users
        self._event_retention_days = event_retention_days
        self._cleanup_interval = cleanup_interval
        self._events_since_cleanup = 0

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        async with self._session_factory() as session:
            data["session"] = session
            current_event_key = event_key(event)
            if current_event_key is not None:
                claimed = await session.execute(
                    pg_insert(ProcessedEvent)
                    .values(event_key=current_event_key)
                    .on_conflict_do_nothing(index_elements=[ProcessedEvent.event_key])
                    .returning(ProcessedEvent.event_key)
                )
                if claimed.scalar_one_or_none() is None:
                    logger.info("Skipping duplicate Telegram event: event_key=%s", current_event_key)
                    return None
                self._events_since_cleanup += 1
                if self._events_since_cleanup >= self._cleanup_interval:
                    cutoff = datetime.now(UTC) - timedelta(days=self._event_retention_days)
                    await session.execute(
                        delete(ProcessedEvent).where(ProcessedEvent.created_at < cutoff)
                    )
                    self._events_since_cleanup = 0
            telegram_user = getattr(event, "from_user", None)
            if telegram_user is not None:
                data["db_user"] = await self._users.get_or_create(session, telegram_user)

            try:
                result = await handler(event, data)
            except Exception:
                await session.rollback()
                raise
            else:
                await session.commit()
                return result
