import re
from collections.abc import Mapping, Sequence

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ConversationMessage, MessageRole

PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?7|8)[\s().-]*(?:\d[\s().-]*){9,10}(?!\w)")
EMAIL_PATTERN = re.compile(r"(?<!\w)[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?!\w)")


def redact_for_ai(content: str) -> str:
    """Keep CRM history intact while hiding direct contact details from the LLM."""

    redacted = PHONE_PATTERN.sub("[телефон скрыт]", content)
    return EMAIL_PATTERN.sub("[email скрыт]", redacted)


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
        max_chars: int | None = None,
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
        if max_chars is None:
            return [
                {"role": message.role, "content": redact_for_ai(message.content)}
                for message in messages
            ]

        selected: list[dict[str, str]] = []
        used_chars = 0
        for message in reversed(messages):
            content = redact_for_ai(message.content)
            remaining_chars = max_chars - used_chars
            if remaining_chars <= 0:
                break
            if len(content) > remaining_chars:
                if not selected:
                    content = content[:remaining_chars]
                else:
                    break
            selected.append({"role": message.role, "content": content})
            used_chars += len(content)
        selected.reverse()
        return selected
