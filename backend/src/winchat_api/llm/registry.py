"""Chat provider selection.

The only place that maps a config string to a concrete vendor. Adding Anthropic or OpenAI
means one entry in `_BUILDERS` — every call site keeps talking to `ChatProvider`.
"""

from collections.abc import Callable
from functools import lru_cache

from winchat_api.config import Settings, get_settings
from winchat_api.llm.base import ChatProvider, ProviderError
from winchat_api.llm.groq_provider import GroqChatProvider


def _build_groq(settings: Settings, model: str, retry_budget_s: float) -> ChatProvider:
    return GroqChatProvider(
        api_key=settings.groq_api_key or "",
        model=model,
        timeout_s=settings.llm_timeout_s,
        retry_budget_s=retry_budget_s,
    )


_BUILDERS: dict[str, Callable[[Settings, str, float], ChatProvider]] = {
    "groq": _build_groq,
}


def available_providers() -> list[str]:
    return sorted(_BUILDERS)


@lru_cache
def build_chat_provider(
    provider: str | None = None,
    model: str | None = None,
    retry_budget_s: float | None = None,
) -> ChatProvider:
    """Build a provider, overriding the configured defaults.

    The eval harness needs both overrides: the judge is pinned to a different model from
    the one under test, and an offline suite can wait out a rate limit far longer than a
    user can. Cached per (provider, model, budget) so repeated calls reuse the client.
    """
    settings = get_settings()
    provider = provider or settings.llm_provider
    builder = _BUILDERS.get(provider)
    if builder is None:
        raise ProviderError(
            f"unknown LLM provider {provider!r}; available: {', '.join(available_providers())}"
        )
    return builder(
        settings,
        model or settings.llm_model,
        settings.llm_retry_budget_s if retry_budget_s is None else retry_budget_s,
    )


def get_chat_provider() -> ChatProvider:
    """The configured provider, built once per process (clients are reused)."""
    return build_chat_provider()
