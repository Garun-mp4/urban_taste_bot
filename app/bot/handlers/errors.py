import logging

from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)


async def handle_error(event: ErrorEvent) -> bool:
    """Log unexpected update failures and return a user-safe message when possible."""

    exception = event.exception
    logger.error(
        "Unhandled update error: %s",
        type(exception).__name__,
        exc_info=(type(exception), exception, exception.__traceback__),
    )
    message = getattr(event.update, "message", None)
    if message is not None:
        try:
            await message.answer("Произошла техническая ошибка. Попробуйте ещё раз позже.")
        except Exception:
            logger.exception("Could not send the generic error message")
    return True
