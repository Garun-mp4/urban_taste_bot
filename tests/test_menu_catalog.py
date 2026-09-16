import json

from app.bot.keyboards import menu as menu_keyboard_module
from app.menu import catalog
from app.telegraph.publisher import section_nodes


def test_menu_keyboard_contains_published_index_and_sections(monkeypatch):
    urls = {section.slug: f"https://telegra.ph/{section.slug}" for section in catalog.MENU_SECTIONS}
    urls["menu"] = "https://telegra.ph/urban-taste-menu"
    monkeypatch.setattr(menu_keyboard_module, "MENU_PAGE_URLS", urls)

    keyboard = menu_keyboard_module.menu_keyboard()

    assert keyboard is not None
    assert keyboard.inline_keyboard[0][0].url == urls["menu"]
    assert sum(len(row) for row in keyboard.inline_keyboard[1:]) == len(catalog.MENU_SECTIONS)


def test_menu_keyboard_is_not_shown_before_pages_are_published(monkeypatch):
    monkeypatch.setattr(menu_keyboard_module, "MENU_PAGE_URLS", {})

    assert menu_keyboard_module.menu_keyboard() is None


def test_confirmed_popular_section_contains_only_known_dishes():
    popular = catalog.get_section("popular")

    assert [dish.name for dish in catalog.get_dishes(popular)] == [
        "Стейк Urban Classic",
        "Паста с морепродуктами",
        "Крем-суп из грибов",
        "Чизкейк Urban",
    ]


def test_empty_section_explains_that_catalogue_data_is_not_confirmed():
    section = catalog.get_section("breakfasts")
    nodes = section_nodes(section, {})
    text = " ".join(str(child) for node in nodes for child in node.get("children", []))

    assert catalog.MENU_EMPTY_SECTION_TEXT in text
    assert not any(node.get("tag") == "img" for node in nodes)


def test_published_manifest_loader_accepts_only_telegraph_https_urls(tmp_path, monkeypatch):
    manifest = tmp_path / "pages.json"
    manifest.write_text(
        json.dumps(
            {
                "menu": "https://telegra.ph/urban-taste-menu",
                "invalid": "https://example.com/menu",
                "number": 42,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(catalog, "MENU_PAGE_MANIFEST", manifest)

    assert catalog._load_page_urls() == {"menu": "https://telegra.ph/urban-taste-menu"}
