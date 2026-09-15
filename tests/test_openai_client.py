import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.ai.openai_client import AIReply, OpenAIClient


def test_parse_structured_reply():
    reply = OpenAIClient._parse_reply(
        '{"answer":"Средний чек — 2500 рублей на человека.","needs_admin":false,"intent":"question"}'
    )

    assert reply == AIReply(
        answer="Средний чек — 2500 рублей на человека.",
        needs_admin=False,
        intent="question",
    )


def test_parse_unknown_intent_as_question():
    reply = OpenAIClient._parse_reply(
        '{"answer":"Уточню у администратора.","needs_admin":"true","intent":"unknown"}'
    )

    assert reply.answer == "Уточню у администратора."
    assert reply.needs_admin is True
    assert reply.intent == "question"


def test_unstructured_model_output_is_escalated():
    reply = OpenAIClient._parse_reply("NEEDS_ADMIN: Уточню это у администратора.")

    assert reply.answer == "Уточню это у администратора."
    assert reply.needs_admin is True


def test_reasoning_configuration_is_sent_to_openai():
    async def run_check():
        client = OpenAIClient(
            api_key="test-key",
            model="gpt-5.6-luna",
            timeout_seconds=5.0,
            reasoning_effort="medium",
        )
        create_completion = AsyncMock(return_value=SimpleNamespace())
        client._client.chat.completions.create = create_completion

        await client._create_completion(
            [{"role": "user", "content": "Проверка"}],
            response_mode="text",
        )

        request = create_completion.await_args.kwargs
        assert request["model"] == "gpt-5.6-luna"
        assert request["reasoning_effort"] == "medium"
        await client.close()

    asyncio.run(run_check())
