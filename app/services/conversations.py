from collections.abc import Mapping, Sequence

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ConversationMessage, MessageRole


class ConversationService:
    async def add_message(
        self,
        session: AsyncSession,
        user_id: int,
        role: MessageRole | str,
        content: str,
    ) -> ConversationMessage:
        role_value = role.value if isinstance(role, MessageRole) else role
        message = ConversationMessage(
            user_id=user_id,
            role=role_value,
            content=content.strip()[:12000],
        )
        session.add(message)
        await session.flush()
        return message

    async def get_ai_history(
        self,
        session: AsyncSession,
        user_id: int,
        limit: int,
    ) -> list[Mapping[str, str]]:
        result = await session.execute(
            select(ConversationMessage)
            .where(
                ConversationMessage.user_id == user_id,
                ConversationMessage.role.in_([MessageRole.USER.value, MessageRole.ASSISTANT.value]),
            )
            .order_by(desc(ConversationMessage.created_at), desc(ConversationMessage.id))
            .limit(limit)
        )
        messages: Sequence[ConversationMessage] = list(reversed(result.scalars().all()))
        return [{"role": message.role, "content": message.content} for message in messages]
