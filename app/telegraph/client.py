"""Small async client for the official Telegraph publishing API."""

import json
from collections.abc import Mapping, Sequence
from typing import Any

import aiohttp


class TelegraphApiError(RuntimeError):
    """Raised when Telegraph rejects a request or returns an invalid response."""


class TelegraphClient:
    API_URL = "https://api.telegra.ph"

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "TelegraphClient":
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # Let aiohttp use the host's configured proxy (including the
            # Windows system proxy used in some desktop deployments).
            self._session = aiohttp.ClientSession(timeout=self._timeout, trust_env=True)
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def _api_request(
        self,
        method: str,
        endpoint: str,
        data: Mapping[str, str],
    ) -> Any:
        session = await self._get_session()
        async with session.request(method, f"{self.API_URL}/{endpoint}", data=data) as response:
            raw_body = await response.text()
            try:
                body = json.loads(raw_body)
            except json.JSONDecodeError as exc:
                raise TelegraphApiError(f"Telegraph returned invalid JSON (HTTP {response.status})") from exc
            if not isinstance(body, dict):
                raise TelegraphApiError("Telegraph response is not a JSON object")
            if response.status >= 400 or not body.get("ok"):
                error = str(body.get("error") or f"HTTP {response.status}")
                raise TelegraphApiError(f"Telegraph API error: {error}")
            if "result" not in body:
                raise TelegraphApiError("Telegraph response has no result")
            return body["result"]

    async def create_account(
        self,
        *,
        short_name: str = "UrbanTaste",
        author_name: str = "Urban Taste",
        author_url: str | None = None,
    ) -> str:
        data = {
            "short_name": short_name[:32],
            "author_name": author_name[:128],
        }
        if author_url:
            data["author_url"] = author_url[:512]
        result = await self._api_request("POST", "createAccount", data)
        access_token = result.get("access_token") if isinstance(result, dict) else None
        if not access_token:
            raise TelegraphApiError("Telegraph account response has no access token")
        return str(access_token)

    async def create_page(
        self,
        access_token: str,
        *,
        title: str,
        content: Sequence[str | Mapping[str, Any]],
        author_name: str = "Urban Taste",
        author_url: str | None = None,
    ) -> dict[str, Any]:
        content_json = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
        if len(content_json.encode("utf-8")) > 64 * 1024:
            raise TelegraphApiError("Telegraph page content exceeds 64 KB")
        data = {
            "access_token": access_token,
            "title": title[:256],
            "author_name": author_name[:128],
            "content": content_json,
            "return_content": "false",
        }
        if author_url:
            data["author_url"] = author_url[:512]
        result = await self._api_request("POST", "createPage", data)
        if not isinstance(result, dict) or not result.get("url"):
            raise TelegraphApiError("Telegraph page response has no URL")
        return result
