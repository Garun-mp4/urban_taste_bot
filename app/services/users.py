from aiogram.types import User as TelegramUser
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.database.models import User


class UserService:
    async def get_or_create(self, session: AsyncSession, telegram_user: TelegramUser) -> User:
        """Upsert Telegram profile data without overwriting a saved phone."""

        statement = pg_insert(User).values(
            telegram_id=telegram_user.id,
            name=telegram_user.full_name[:255],
            username=telegram_user.username,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[User.telegram_id],
            set_={
                "name": statement.excluded.name,
                "username": statement.excluded.username,
                "updated_at": func.now(),
            },
        ).returning(User)
        return (await session.execute(statement)).scalar_one()

    async def update_phone(self, session: AsyncSession, user: User, phone: str) -> None:
        user.phone = phone
        await session.flush()
