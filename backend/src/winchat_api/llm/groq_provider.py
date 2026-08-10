"""Groq chat provider, the default generation backend. The only module that talks to the
Groq SDK.
"""

from collections.abc import AsyncIterator, Sequence

from groq import APIError, AsyncGroq

from winchat_api.llm.base import ChatProvider, Completion, Message, ProviderError
from winchat_api.llm.retry import with_rate_limit_retry


class GroqChatProvider(ChatProvider):
    name = "groq"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_s: float = 30.0,
        retry_budget_s: float = 20.0,
    ) -> None:
        if not api_key:
            raise ProviderError("GROQ_API_KEY is not set")
        self.model = model
        self._retry_budget_s = retry_budget_s
        # SDK retries are disabled: `with_rate_limit_retry` owns the schedule, because a
        # token-per-minute budget needs waits far longer than the SDK is willing to take.
        self._client = AsyncGroq(api_key=api_key, timeout=timeout_s, max_retries=0)

    @staticmethod
    def _to_payload(messages: Sequence[Message]) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        json_object: bool = False,
    ) -> Completion:
        extra = {"response_format": {"type": "json_object"}} if json_object else {}
        try:
            response = await with_rate_limit_retry(
                lambda: self._client.chat.completions.create(
                    model=self.model,
                    messages=self._to_payload(messages),
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **extra,
                ),
                budget_s=self._retry_budget_s,
                label=f"groq/{self.model}",
            )
        except APIError as exc:  # surface a clean message, never the raw SDK traceback
            raise ProviderError(f"groq: {exc.message}") from exc

        usage = response.usage
        return Completion(
            text=response.choices[0].message.content or "",
            model=response.model,
            provider=self.name,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
        )

    async def stream(
        self,
        messages: Sequence[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        try:
            # Retried only up to the first token. Once bytes are flowing, a retry would
            # replay text the user has already seen.
            stream = await with_rate_limit_retry(
                lambda: self._client.chat.completions.create(
                    model=self.model,
                    messages=self._to_payload(messages),
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                ),
                budget_s=self._retry_budget_s,
                label=f"groq/{self.model}",
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except APIError as exc:
            raise ProviderError(f"groq: {exc.message}") from exc
