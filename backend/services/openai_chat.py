from __future__ import annotations

from typing import Any, Iterable

import httpx
from openai import AsyncOpenAI

from backend.core.config import settings
from backend.database.models import ChatMessage, MessageRole


class ChatProviderError(RuntimeError):
    def __init__(self, user_message: str, log_message: str, code: str = "generic") -> None:
        super().__init__(log_message)
        self.user_message = user_message
        self.log_message = log_message
        self.code = code


class TimewebChatService:
    def __init__(self) -> None:
        http_client = httpx.AsyncClient(trust_env=False, timeout=60.0)
        base_url = (
            f"{settings.TIMEWEB_BASE_URL.rstrip('/')}/api/v1/cloud-ai/agents/"
            f"{settings.TIMEWEB_AGENT_ACCESS_ID}/v1"
        )
        self._client = AsyncOpenAI(
            api_key=settings.TIMEWEB_API_KEY,
            base_url=base_url,
            default_headers={"x-proxy-source": settings.TIMEWEB_PROXY_SOURCE},
            http_client=http_client,
        )

    async def generate_reply(
        self,
        history: Iterable[ChatMessage],
        latest_user_content: str | list[dict[str, Any]] | None = None,
    ) -> str:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": settings.TIMEWEB_SYSTEM_PROMPT}
        ]
        for message in history:
            if message.role == MessageRole.USER:
                role = "user"
            elif message.role == MessageRole.ASSISTANT:
                role = "assistant"
            else:
                continue
            messages.append({"role": role, "content": message.content})
        if latest_user_content is not None:
            messages.append({"role": "user", "content": latest_user_content})

        try:
            response = await self._client.chat.completions.create(
                model=settings.TIMEWEB_MODEL,
                messages=messages,
                temperature=0.7,
            )
        except Exception as exc:  # provider errors mapping
            status_code = getattr(exc, "status_code", None)
            detail = str(exc)
            if status_code == 401:
                raise ChatProviderError(
                    user_message="Ошибка авторизации у AI-провайдера. Проверьте API-ключ.",
                    log_message=f"Timeweb auth error (401): {detail}",
                    code="auth",
                ) from exc
            if status_code == 403:
                raise ChatProviderError(
                    user_message="AI-провайдер отклонил доступ. Проверьте токен и права агента Timeweb.",
                    log_message=f"Timeweb permission error (403): {detail}",
                    code="auth",
                ) from exc
            if status_code == 429:
                raise ChatProviderError(
                    user_message="Превышен лимит запросов к AI-провайдеру. Попробуйте чуть позже.",
                    log_message=f"Timeweb rate limit error (429): {detail}",
                    code="rate_limit",
                ) from exc
            if status_code is not None and int(status_code) >= 400:
                raise ChatProviderError(
                    user_message="Запрос к AI-провайдеру завершился ошибкой. Попробуйте позже.",
                    log_message=f"Timeweb HTTP error ({status_code}): {detail}",
                    code="http",
                ) from exc
            raise ChatProviderError(
                user_message="AI-провайдер временно недоступен. Попробуйте позже.",
                log_message=f"Timeweb transport/runtime error: {detail}",
                code="transport",
            ) from exc

        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            raise ValueError("Timeweb returned an empty response")
        return answer

    async def close(self) -> None:
        await self._client.close()

#For older imports compatibility
GroqChatService = TimewebChatService
GeminiChatService = TimewebChatService
OpenAIChatService = TimewebChatService
