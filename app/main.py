import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from redis.asyncio import Redis, from_url

from app.ai.openai_client import OpenAIClient
from app.bot.handlers import admin, booking, common
from app.bot.handlers.errors import handle_error
from app.bot.middlewares.database import DatabaseSessionMiddleware
from app.bot.middlewares.rate_limit import RateLimitMiddleware
from app.config import get_settings
from app.database.database import Database
from app.logging_config import configure_logging
from app.services.container import ServiceContainer
from app.services.conversations import ConversationService
from app.services.notifications import AdminNotificationService, NotificationWorker
from app.services.requests import RequestService
from app.services.users import UserService

logger = logging.getLogger(__name__)


async def configure_bot_commands(bot: Bot, admin_chat_id: int) -> None:
    """Expose only relevant commands in the client and administrator menus."""

    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Открыть главное меню"),
                BotCommand(command="my_requests", description="Мои заявки"),
                BotCommand(command="cancel", description="Отменить текущий сценарий"),
            ],
            scope=BotCommandScopeDefault(),
        )
        await bot.set_my_commands(
            [
                BotCommand(command="stats", description="Статистика CRM"),
                BotCommand(command="new_requests", description="Новые заявки"),
                BotCommand(command="requests", description="Поиск заявок"),
                BotCommand(command="request", description="Заявка и история по ID"),
            ],
            scope=BotCommandScopeChat(chat_id=admin_chat_id),
        )
    except Exception:
        logger.warning("Could not configure Telegram command menus", exc_info=True)


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
    rate_limit_redis: Redis | None = None
    ai_client: OpenAIClient | None = None
    notification_worker_task: asyncio.Task[None] | None = None

    try:
        await database.wait_until_ready()

        bot = Bot(
            token=settings.telegram_bot_token.get_secret_value(),
            default=DefaultBotProperties(parse_mode=None),
        )
        storage = RedisStorage.from_url(settings.redis_url)
        rate_limit_redis = from_url(settings.redis_url)
        ai_client = OpenAIClient(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.openai_model,
            timeout_seconds=settings.ai_timeout_seconds,
            reasoning_effort=settings.openai_reasoning_effort,
        )
        notifications = AdminNotificationService(bot, settings.admin_chat_id)
        services = ServiceContainer(
            users=UserService(),
            conversations=ConversationService(),
            requests=RequestService(
                timezone=settings.timezone,
                capacity=settings.reservation_capacity,
                max_guests=settings.reservation_max_guests,
                duration_minutes=settings.reservation_duration_minutes,
                slot_interval_minutes=settings.reservation_slot_interval_minutes,
                min_advance_minutes=settings.reservation_min_advance_minutes,
                max_days=settings.reservation_max_days,
            ),
            notifications=notifications,
            ai=ai_client,
        )

        dispatcher = Dispatcher(storage=storage, settings=settings, services=services)
        database_middleware = DatabaseSessionMiddleware(
            database.session_factory,
            services.users,
            event_retention_days=settings.processed_event_retention_days,
        )
        dispatcher.message.outer_middleware(
            RateLimitMiddleware(rate_limit_redis, settings.rate_limit_seconds)
        )
        dispatcher.callback_query.outer_middleware(
            RateLimitMiddleware(rate_limit_redis, settings.rate_limit_seconds)
        )
        dispatcher.message.outer_middleware(database_middleware)
        dispatcher.callback_query.outer_middleware(database_middleware)

        dispatcher.include_router(admin.router)
        dispatcher.include_router(common.router)
        dispatcher.include_router(booking.router)
        dispatcher.errors.register(handle_error)

        notification_worker_task = asyncio.create_task(
            NotificationWorker(
                notifications,
                database.session_factory,
                settings.notification_poll_seconds,
                settings.notification_max_attempts,
            ).run()
        )
        logger.info("Urban Taste bot started with model=%s", settings.openai_model)
        await bot.delete_webhook(drop_pending_updates=settings.drop_pending_updates)
        await configure_bot_commands(bot, settings.admin_chat_id)
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        if notification_worker_task is not None:
            notification_worker_task.cancel()
            try:
                await notification_worker_task
            except asyncio.CancelledError:
                pass
        if ai_client is not None:
            await ai_client.close()
        if storage is not None:
            await storage.close()
        if rate_limit_redis is not None:
            await rate_limit_redis.aclose()
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
