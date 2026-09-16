"""Single source of truth for facts exposed by the Urban Taste assistant."""

BUSINESS_NAME = "Urban Taste"
BUSINESS_DESCRIPTION = "Современный городской ресторан европейской кухни."
ADDRESS = "ул. Центральная, 15"
OPENING_HOURS = (
    "понедельник–пятница: 10:00–23:00; суббота–воскресенье: 11:00–00:00"
)
MENU_SECTIONS = (
    "завтраки",
    "бизнес-ланчи",
    "основные блюда европейской кухни",
    "десерты",
    "напитки",
    "вегетарианские блюда",
)
POPULAR_DISHES = (
    "стейк Urban Classic",
    "паста с морепродуктами",
    "крем-суп из грибов",
    "чизкейк Urban",
)
AVERAGE_CHECK = "2500 рублей на человека"
SERVICES = (
    "бронирование столиков",
    "проведение мероприятий",
    "доставка еды",
    "подарочные сертификаты",
)

BUSINESS_KNOWLEDGE_TEXT = f"""\
- Название: {BUSINESS_NAME}.
- Формат: {BUSINESS_DESCRIPTION}
- Описание: ресторан современной европейской кухни в центре города.
- Адрес: {ADDRESS}.
- Часы работы: {OPENING_HOURS}.
- Разделы меню: {", ".join(MENU_SECTIONS)}.
- Популярные блюда: {", ".join(POPULAR_DISHES)}.
- Средний чек: {AVERAGE_CHECK}.
- Услуги: {", ".join(SERVICES)}.
""".strip()

MENU_TEXT = (
    f"Меню {BUSINESS_NAME} включает:\n"
    + "\n".join(f"• {section}" for section in MENU_SECTIONS)
    + f"\n\nПопулярные блюда: {', '.join(POPULAR_DISHES)}."
    + f"\n\nСредний чек — {AVERAGE_CHECK}."
)

INFO_TEXT = (
    f"{BUSINESS_NAME} — {BUSINESS_DESCRIPTION.lower()}\n\n"
    f"Адрес: {ADDRESS}\n"
    "Пн–Пт: 10:00–23:00\n"
    "Сб–Вс: 11:00–00:00"
)
