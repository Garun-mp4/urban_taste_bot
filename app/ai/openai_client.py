import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from app.ai.prompts import BUSINESS_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class AIServiceError(RuntimeError):
    """Raised when the OpenAI request cannot produce a usable answer."""


@dataclass(frozen=True, slots=True)
class AIReply:
    answer: str
    needs_admin: bool = False
    intent: str = "question"


class OpenAIClient:
    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        self._model = model
        self._client = AsyncOpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=2,
        )

    async def answer(self, history: Sequence[Mapping[str, str]]) -> AIReply:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": BUSINESS_SYSTEM_PROMPT},
            *[{"role": item["role"], "content": item["content"]} for item in history],
        ]

        try:
            completion = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                response_format={"type": "json_object"},
                max_completion_tokens=700,
            )
        except Exception as exc:
            logger.warning("OpenAI request failed for model %s: %s", self._model, type(exc).__name__)
            raise AIServiceError("OpenAI request failed") from exc

        content = completion.choices[0].message.content if completion.choices else None
        if not content:
            raise AIServiceError("OpenAI returned an empty response")
        return self._parse_reply(content)

    @staticmethod
    def _parse_reply(content: str) -> AIReply:
        raw_content = content.strip()
        try:
            payload: Any = json.loads(raw_content)
        except json.JSONDecodeError:
            # A configurable model may ignore JSON mode. Preserve the answer,
            # but escalate it so an unstructured response is never trusted as
            # a fully qualified business answer.
            if raw_content.startswith("NEEDS_ADMIN:"):
                raw_content = raw_content.removeprefix("NEEDS_ADMIN:").strip()
            return AIReply(answer=raw_content, needs_admin=True)

        if not isinstance(payload, dict):
            raise AIServiceError("OpenAI returned an invalid response shape")

        answer = str(payload.get("answer", "")).strip()
        if not answer:
            raise AIServiceError("OpenAI returned an empty answer")

        needs_admin = OpenAIClient._as_bool(payload.get("needs_admin", False))
        intent = str(payload.get("intent", "question")).strip().lower()
        if intent not in {"question", "reservation", "other"}:
            intent = "question"
        return AIReply(answer=answer, needs_admin=needs_admin, intent=intent)

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "да"}

    async def close(self) -> None:
        await self._client.close()
