import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, url: str, pool_size: int, max_overflow: int) -> None:
        self.engine: AsyncEngine = create_async_engine(
            url,
            pool_pre_ping=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
            connect_args={"server_settings": {"application_name": "urban_taste_bot"}},
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    async def wait_until_ready(self, retries: int = 20) -> None:
        """Wait for PostgreSQL to become available after Compose starts it."""

        for attempt in range(1, retries + 1):
            try:
                async with self.engine.begin() as connection:
                    await connection.execute(text("SELECT 1"))
                logger.info("PostgreSQL connection is ready")
                return
            except SQLAlchemyError:
                if attempt == retries:
                    logger.exception("PostgreSQL did not become ready after %s attempts", retries)
                    raise
                delay = min(attempt, 5)
                logger.warning("Waiting for PostgreSQL (%s/%s); retrying in %ss", attempt, retries, delay)
                await asyncio.sleep(delay)

    async def dispose(self) -> None:
        await self.engine.dispose()
