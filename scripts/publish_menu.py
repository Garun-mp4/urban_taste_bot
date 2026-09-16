"""Publish the local menu catalogue and print the generated page manifest."""

import asyncio
import json

from app.config import get_settings
from app.menu.catalog import MENU_PAGE_MANIFEST
from app.telegraph.publisher import publish_catalog


async def main() -> None:
    settings = get_settings()
    access_token = (
        settings.telegraph_access_token.get_secret_value()
        if settings.telegraph_access_token is not None
        else None
    )
    if not settings.menu_image_base_url:
        raise RuntimeError(
            "MENU_IMAGE_BASE_URL is required. Point it at a public HTTPS directory "
            "containing assets/menu/*.png."
        )
    page_urls = await publish_catalog(
        access_token,
        image_base_url=settings.menu_image_base_url,
    )
    MENU_PAGE_MANIFEST.write_text(
        json.dumps(page_urls, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(page_urls, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
