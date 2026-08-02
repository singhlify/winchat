"""Groq chat provider — the default generation backend.

Groq serves open-weight models (Llama / Qwen class) fast and cheaply. We talk to the
vendor SDK here and nowhere else; the rest of the app only knows `ChatProvider`.
"""

from collections.abc import AsyncIterator, Sequence

from groq import APIError, AsyncGroq

from winchat_api.llm.base import ChatProvider, Completion, Message, ProviderError


class GroqChatProvider(ChatProvider):
    name = "groq"

    def __init__(self, *, api_key: str, model: str, timeout_s: float = 30.0) -> None:
        if not api_key:
            raise ProviderError("GROQ_API_KEY is not set")
        self.model = model
        self._client = AsyncGroq(api_key=api_key, timeout=timeout_s)

    @staticmethod
    def _to_payload(messages: Sequence[Message]) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> Completion:
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=self._to_payload(messages),
                temperature=temperature,
                max_tokens=max_tokens,
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
            stream = await self._client.chat.completions.create(
                model=self.model,
                messages=self._to_payload(messages),
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except APIError as exc:
            raise ProviderError(f"groq: {exc.message}") from exc
