import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """Limit bursts from one Telegram user before they reach the database or AI."""

    def __init__(self, redis: Redis, window_seconds: float) -> None:
        self._redis = redis
        self._window_ms = max(1, int(window_seconds * 1000))

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        telegram_user = getattr(event, "from_user", None)
        if telegram_user is None:
            return await handler(event, data)

        key = f"urban_taste:rate:{telegram_user.id}"
        try:
            allowed = await self._redis.set(key, "1", px=self._window_ms, nx=True)
        except RedisError:
            # Redis is an abuse-control dependency, not a reason to make the
            # restaurant unavailable when the cache has a transient outage.
            logger.warning("Rate limiter Redis is unavailable; allowing the update", exc_info=True)
            return await handler(event, data)
        if allowed:
            return await handler(event, data)

        if isinstance(event, Message):
            await event.answer("Пожалуйста, отправляйте сообщения чуть медленнее.")
        elif isinstance(event, CallbackQuery):
            await event.answer("Пожалуйста, подождите секунду.", show_alert=False)
        return None
