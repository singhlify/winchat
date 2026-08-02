"""Chat provider selection.

The only place that maps a config string to a concrete vendor. Adding Anthropic or OpenAI
means one entry in `_BUILDERS` — every call site keeps talking to `ChatProvider`.
"""

from collections.abc import Callable
from functools import lru_cache

from winchat_api.config import Settings, get_settings
from winchat_api.llm.base import ChatProvider, ProviderError
from winchat_api.llm.groq_provider import GroqChatProvider


def _build_groq(settings: Settings) -> ChatProvider:
    return GroqChatProvider(
        api_key=settings.groq_api_key or "",
        model=settings.llm_model,
        timeout_s=settings.llm_timeout_s,
    )


_BUILDERS: dict[str, Callable[[Settings], ChatProvider]] = {
    "groq": _build_groq,
}


def available_providers() -> list[str]:
    return sorted(_BUILDERS)


@lru_cache
def get_chat_provider() -> ChatProvider:
    """The configured provider, built once per process (clients are reused)."""
    settings = get_settings()
    builder = _BUILDERS.get(settings.llm_provider)
    if builder is None:
        raise ProviderError(
            f"unknown LLM_PROVIDER {settings.llm_provider!r}; "
            f"available: {', '.join(available_providers())}"
        )
    return builder(settings)
