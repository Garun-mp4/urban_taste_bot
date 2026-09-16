import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.conversations import ConversationService, redact_for_ai


def test_contact_details_are_redacted_only_for_ai_context():
    content = "Позвоните мне: 8 (900) 123-45-67 или test@example.com"

    redacted = redact_for_ai(content)

    assert "8 (900) 123-45-67" not in redacted
    assert "test@example.com" not in redacted
    assert "[телефон скрыт]" in redacted
    assert "[email скрыт]" in redacted


def test_ai_history_keeps_latest_messages_within_character_budget():
    async def run_check():
        rows = [
            SimpleNamespace(role="assistant", content="самый свежий ответ"),
            SimpleNamespace(role="user", content="первый вопрос"),
            SimpleNamespace(role="assistant", content="старый ответ"),
        ]
        result = SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: rows),
        )
        session = SimpleNamespace(execute=AsyncMock(return_value=result))

        history = await ConversationService().get_ai_history(
            session,
            user_id=1,
            limit=12,
            max_chars=len("самый свежий ответ") + 2,
        )

        assert history == [{"role": "assistant", "content": "самый свежий ответ"}]

    asyncio.run(run_check())
