from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.menu.catalog import MENU_PAGE_URLS, MENU_SECTIONS


def menu_keyboard() -> InlineKeyboardMarkup | None:
    """Build a compact two-column menu launcher from published page URLs."""

    buttons = [
        InlineKeyboardButton(text=section.button_label, url=MENU_PAGE_URLS[section.slug])
        for section in MENU_SECTIONS
        if MENU_PAGE_URLS.get(section.slug)
    ]
    if not buttons:
        return None

    rows = (
        [[InlineKeyboardButton(text="🍽 Открыть всё меню", url=MENU_PAGE_URLS["menu"])]]
        if MENU_PAGE_URLS.get("menu")
        else []
    )
    rows.extend(buttons[index : index + 2] for index in range(0, len(buttons), 2))
    return InlineKeyboardMarkup(inline_keyboard=rows)
