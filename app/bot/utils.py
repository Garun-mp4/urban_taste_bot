from collections.abc import Iterable

from aiogram.types import Message, ReplyKeyboardMarkup


def split_text(text: str, max_length: int = 4000) -> Iterable[str]:
    """Split a response into Telegram-safe chunks, preferring line breaks."""

    remaining = text.strip()
    while len(remaining) > max_length:
        split_at = remaining.rfind("\n", 0, max_length)
        if split_at < max_length // 2:
            split_at = max_length
        yield remaining[:split_at].rstrip()
        remaining = remaining[split_at:].lstrip()
    if remaining:
        yield remaining


async def answer_in_chunks(
    message: Message,
    text: str,
    *,
    reply_markup: ReplyKeyboardMarkup | None = None,
) -> None:
    chunks = list(split_text(text)) or ["Извините, не удалось сформировать ответ."]
    for index, chunk in enumerate(chunks):
        await message.answer(
            chunk,
            reply_markup=reply_markup if index == len(chunks) - 1 else None,
        )
