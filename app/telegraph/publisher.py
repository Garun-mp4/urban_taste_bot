"""Build and publish the structured Urban Taste catalogue to Telegraph."""

from collections.abc import Mapping
from urllib.parse import quote

from app.menu.catalog import (
    MENU_DISHES,
    MENU_EMPTY_SECTION_TEXT,
    MENU_SECTIONS,
    MenuDish,
    MenuSection,
    get_dishes,
)
from app.telegraph.client import TelegraphClient


def dish_nodes(dish: MenuDish, image_url: str) -> list[dict[str, object]]:
    return [
        {"tag": "h3", "children": [dish.name]},
        {"tag": "img", "attrs": {"src": image_url}},
        {"tag": "p", "children": [dish.description]},
    ]


def section_nodes(section: MenuSection, image_urls: Mapping[str, str]) -> list[dict[str, object]]:
    nodes: list[dict[str, object]] = [
        {"tag": "p", "children": [section.description]},
        {
            "tag": "p",
            "children": ["Актуальные цены и состав блюд уточняйте у администратора Urban Taste."],
        },
    ]
    dishes = get_dishes(section)
    if not dishes:
        nodes.append({"tag": "p", "children": [MENU_EMPTY_SECTION_TEXT]})
        return nodes
    for dish in dishes:
        image_url = image_urls.get(dish.slug)
        if image_url:
            nodes.extend(dish_nodes(dish, image_url))
    return nodes


def menu_index_nodes(page_urls: Mapping[str, str]) -> list[dict[str, object]]:
    links = [
        {
            "tag": "li",
            "children": [
                {
                    "tag": "a",
                    "attrs": {"href": page_urls[section.slug]},
                    "children": [section.title],
                }
            ],
        }
        for section in MENU_SECTIONS
        if page_urls.get(section.slug)
    ]
    return [
        {
            "tag": "p",
            "children": ["Urban Taste — современный городской ресторан европейской кухни в центре города."],
        },
        {
            "tag": "p",
            "children": ["Выберите раздел, чтобы открыть подробную витрину блюд."],
        },
        {"tag": "ul", "children": links},
        {
            "tag": "p",
            "children": ["Адрес: ул. Центральная, 15. Средний чек — 2500 рублей на человека."],
        },
    ]


def build_image_urls(image_base_url: str) -> dict[str, str]:
    """Build public image URLs used by Telegraph ``img`` nodes."""

    base_url = image_base_url.strip().rstrip("/")
    if not base_url.startswith("https://"):
        raise ValueError("MENU_IMAGE_BASE_URL must be a public HTTPS URL")
    return {
        dish.slug: f"{base_url}/{quote(dish.image_filename)}"
        for dish in MENU_DISHES
        if dish.image_path.is_file()
    }


async def publish_catalog(
    access_token: str | None = None,
    *,
    image_base_url: str,
) -> dict[str, str]:
    async with TelegraphClient() as client:
        token = access_token or await client.create_account()
        image_urls = build_image_urls(image_base_url)
        if len(image_urls) != len(MENU_DISHES):
            raise FileNotFoundError("One or more confirmed menu image assets are missing")
        page_urls: dict[str, str] = {}
        for section in MENU_SECTIONS:
            page = await client.create_page(
                token,
                title=f"Urban Taste — {section.title}",
                content=section_nodes(section, image_urls),
            )
            page_urls[section.slug] = str(page["url"])

        index_page = await client.create_page(
            token,
            title="Urban Taste — меню",
            content=menu_index_nodes(page_urls),
        )
        page_urls["menu"] = str(index_page["url"])
        return page_urls
