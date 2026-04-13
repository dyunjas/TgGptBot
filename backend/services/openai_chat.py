from __future__ import annotations

from typing import Iterable

from openai import AsyncOpenAI

from backend.core.config import settings
from backend.database.models import ChatMessage, MessageRole


class OpenAIChatService:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.GPT_API_TOKEN)

    async def generate_reply(self, history: Iterable[ChatMessage]) -> str:
        input_messages = [
            {
                "role": MessageRole.SYSTEM.value,
                "content": [{"type": "input_text", "text": settings.OPENAI_SYSTEM_PROMPT}],
            }
        ]

        for message in history:
            input_messages.append(
                {
                    "role": message.role.value,
                    "content": [{"type": "input_text", "text": message.content}],
                }
            )

        response = await self._client.responses.create(
            model=settings.OPENAI_MODEL,
            input=input_messages,
        )

        answer = (response.output_text or "").strip()
        if not answer:
            raise ValueError("OpenAI returned an empty response")
        return answer

    async def close(self) -> None:
        await self._client.close()
