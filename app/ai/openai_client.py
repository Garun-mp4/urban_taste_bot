import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from openai import AsyncOpenAI, BadRequestError

from app.ai.prompts import BUSINESS_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

REPLY_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "urban_taste_reply",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "needs_admin": {"type": "boolean"},
                "intent": {"type": "string", "enum": ["question", "reservation", "other"]},
            },
            "required": ["answer", "needs_admin", "intent"],
            "additionalProperties": False,
        },
    },
}


class AIServiceError(RuntimeError):
    """Raised when the OpenAI request cannot produce a usable answer."""


@dataclass(frozen=True, slots=True)
class AIReply:
    answer: str
    needs_admin: bool = False
    intent: str = "question"


class OpenAIClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float,
        reasoning_effort: str = "medium",
    ) -> None:
        self._model = model
        self._reasoning_effort = reasoning_effort.strip()
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

        completion = await self._request_with_fallback(messages)

        content = completion.choices[0].message.content if completion.choices else None
        if not content:
            raise AIServiceError("OpenAI returned an empty response")
        return self._parse_reply(content)

    async def _request_with_fallback(self, messages: list[dict[str, str]]) -> Any:
        last_bad_request: BadRequestError | None = None
        for response_mode in ("schema", "json", "text"):
            try:
                return await self._create_completion(messages, response_mode=response_mode)
            except BadRequestError as exc:
                last_bad_request = exc
                if response_mode == "schema":
                    logger.warning("Model %s rejected JSON Schema; retrying with JSON mode", self._model)
                elif response_mode == "json":
                    logger.warning("Model %s rejected JSON mode; retrying with plain text", self._model)
            except Exception as exc:
                logger.warning("OpenAI request failed for model %s: %s", self._model, type(exc).__name__)
                raise AIServiceError("OpenAI request failed") from exc

        logger.warning("OpenAI response format fallback failed for model %s", self._model)
        raise AIServiceError("OpenAI request failed") from last_bad_request

    async def _create_completion(
        self,
        messages: list[dict[str, str]],
        *,
        response_mode: Literal["schema", "json", "text"],
    ) -> Any:
        request: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_completion_tokens": 700,
        }
        if self._reasoning_effort:
            request["reasoning_effort"] = self._reasoning_effort
        if response_mode == "schema":
            request["response_format"] = REPLY_RESPONSE_FORMAT
        elif response_mode == "json":
            request["response_format"] = {"type": "json_object"}
        return await self._client.chat.completions.create(**request)

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
