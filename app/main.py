import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage

from app.ai.openai_client import OpenAIClient
from app.bot.handlers import admin, booking, common
from app.bot.handlers.errors import handle_error
from app.bot.middlewares.database import DatabaseSessionMiddleware
from app.config import get_settings
from app.database.database import Database
from app.logging_config import configure_logging
from app.services.container import ServiceContainer
from app.services.conversations import ConversationService
from app.services.notifications import AdminNotificationService
from app.services.requests import RequestService
from app.services.users import UserService

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    database = Database(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )
    bot: Bot | None = None
    storage: RedisStorage | None = None
    ai_client: OpenAIClient | None = None

    try:
        await database.wait_until_ready()
        await database.create_schema()

        bot = Bot(
            token=settings.telegram_bot_token.get_secret_value(),
            default=DefaultBotProperties(parse_mode=None),
        )
        storage = RedisStorage.from_url(settings.redis_url)
        ai_client = OpenAIClient(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.openai_model,
            timeout_seconds=settings.ai_timeout_seconds,
        )
        services = ServiceContainer(
            users=UserService(),
            conversations=ConversationService(),
            requests=RequestService(),
            notifications=AdminNotificationService(bot, settings.admin_chat_id),
            ai=ai_client,
        )

        dispatcher = Dispatcher(storage=storage, settings=settings, services=services)
        database_middleware = DatabaseSessionMiddleware(database.session_factory, services.users)
        dispatcher.message.outer_middleware(database_middleware)
        dispatcher.callback_query.outer_middleware(database_middleware)

        dispatcher.include_router(admin.router)
        dispatcher.include_router(common.router)
        dispatcher.include_router(booking.router)
        dispatcher.errors.register(handle_error)

        logger.info("Urban Taste bot started with model=%s", settings.openai_model)
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        if ai_client is not None:
            await ai_client.close()
        if storage is not None:
            await storage.close()
        if bot is not None:
            await bot.session.close()
        await database.dispose()
        logger.info("Urban Taste bot stopped")


def main() -> None:
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown requested")


if __name__ == "__main__":
    main()
