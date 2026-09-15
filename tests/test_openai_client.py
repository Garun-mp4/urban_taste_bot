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
