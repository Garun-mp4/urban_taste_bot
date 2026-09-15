from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.users import UserService


class DatabaseSessionMiddleware(BaseMiddleware):
    """Give every message/callback handler one transaction-scoped session."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], users: UserService) -> None:
        self._session_factory = session_factory
        self._users = users

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        async with self._session_factory() as session:
            data["session"] = session
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
