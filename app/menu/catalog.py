"""The confirmed Urban Taste menu catalogue.

Only dishes explicitly supplied in the business brief are published as cards.
Adding a new dish here is the single source of truth for its title, description,
image asset and the sections where it should appear.
"""

import json
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MENU_ASSETS_DIR = PROJECT_ROOT / "assets" / "menu"
MENU_PAGE_MANIFEST = MENU_ASSETS_DIR / "pages.json"

MENU_INTRO_TEXT = (
    "Выберите раздел меню Urban Taste. Откроется отдельная Telegraph-страница "
    "с фотографиями и описанием подтверждённых позиций."
)
MENU_EMPTY_SECTION_TEXT = (
    "Подробный перечень позиций этого раздела ещё не внесён в цифровое меню. "
    "Актуальный ассортимент и цены можно уточнить у администратора Urban Taste."
)


@dataclass(frozen=True, slots=True)
class MenuDish:
    slug: str
    name: str
    description: str
    image_filename: str
    sections: tuple[str, ...]

    @property
    def image_path(self) -> Path:
        return MENU_ASSETS_DIR / self.image_filename


@dataclass(frozen=True, slots=True)
class MenuSection:
    slug: str
    title: str
    button_label: str
    description: str
    dish_slugs: tuple[str, ...] = ()


MENU_DISHES = (
    MenuDish(
        slug="urban-classic",
        name="Стейк Urban Classic",
        description=(
            "Популярное блюдо Urban Taste. Актуальный состав и стоимость уточняйте у администратора."
        ),
        image_filename="urban-classic.png",
        sections=("popular", "main"),
    ),
    MenuDish(
        slug="seafood-pasta",
        name="Паста с морепродуктами",
        description=(
            "Популярная позиция современной европейской кухни. Актуальный состав и "
            "стоимость уточняйте у администратора."
        ),
        image_filename="seafood-pasta.png",
        sections=("popular", "main"),
    ),
    MenuDish(
        slug="mushroom-cream-soup",
        name="Крем-суп из грибов",
        description=(
            "Популярная позиция Urban Taste. Актуальный состав и стоимость уточняйте у администратора."
        ),
        image_filename="mushroom-cream-soup.png",
        sections=("popular", "soups"),
    ),
    MenuDish(
        slug="urban-cheesecake",
        name="Чизкейк Urban",
        description=(
            "Популярный десерт Urban Taste. Актуальный состав и стоимость уточняйте у администратора."
        ),
        image_filename="urban-cheesecake.png",
        sections=("popular", "desserts"),
    ),
)

MENU_SECTIONS = (
    MenuSection(
        slug="popular",
        title="Популярные блюда",
        button_label="⭐ Популярное",
        description="Четыре блюда, которые Urban Taste выделяет среди популярных.",
        dish_slugs=("urban-classic", "seafood-pasta", "mushroom-cream-soup", "urban-cheesecake"),
    ),
    MenuSection(
        slug="main",
        title="Основные блюда",
        button_label="🔥 Основные блюда",
        description="Основные блюда современной европейской кухни.",
        dish_slugs=("urban-classic", "seafood-pasta"),
    ),
    MenuSection(
        slug="soups",
        title="Супы",
        button_label="🥣 Супы",
        description="Тёплые блюда европейской кухни.",
        dish_slugs=("mushroom-cream-soup",),
    ),
    MenuSection(
        slug="desserts",
        title="Десерты",
        button_label="🍰 Десерты",
        description="Десерты Urban Taste.",
        dish_slugs=("urban-cheesecake",),
    ),
    MenuSection(
        slug="breakfasts",
        title="Завтраки",
        button_label="🌤 Завтраки",
        description="Утренний раздел меню Urban Taste.",
    ),
    MenuSection(
        slug="business-lunches",
        title="Бизнес-ланчи",
        button_label="🥗 Бизнес-ланчи",
        description="Дневные предложения Urban Taste.",
    ),
    MenuSection(
        slug="drinks",
        title="Напитки",
        button_label="🥤 Напитки",
        description="Напитки ресторана Urban Taste.",
    ),
    MenuSection(
        slug="vegetarian",
        title="Вегетарианские блюда",
        button_label="🌿 Вегетарианское",
        description="Вегетарианские блюда Urban Taste.",
    ),
)

DISH_BY_SLUG = {dish.slug: dish for dish in MENU_DISHES}
SECTION_BY_SLUG = {section.slug: section for section in MENU_SECTIONS}


def _load_page_urls() -> dict[str, str]:
    """Load the generated Telegraph URL manifest, if the menu was published."""

    try:
        payload = json.loads(MENU_PAGE_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in payload.items()
        if isinstance(key, str) and isinstance(value, str) and value.startswith("https://telegra.ph/")
    }


# Filled by scripts/publish_menu.py. Keeping the manifest on disk makes bot
# startup independent from Telegraph availability and avoids duplicate pages
# on every container restart.
MENU_PAGE_URLS = _load_page_urls()


def get_section(slug: str) -> MenuSection:
    return SECTION_BY_SLUG[slug]


def get_dishes(section: MenuSection) -> tuple[MenuDish, ...]:
    return tuple(DISH_BY_SLUG[slug] for slug in section.dish_slugs)
