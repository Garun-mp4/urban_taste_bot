from app.services.conversations import redact_for_ai


def test_contact_details_are_redacted_only_for_ai_context():
    content = "Позвоните мне: 8 (900) 123-45-67 или test@example.com"

    redacted = redact_for_ai(content)

    assert "8 (900) 123-45-67" not in redacted
    assert "test@example.com" not in redacted
    assert "[телефон скрыт]" in redacted
    assert "[email скрыт]" in redacted
