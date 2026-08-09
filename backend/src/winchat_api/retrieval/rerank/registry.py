"""Reranker selection, same shape as the LLM and embedding registries."""

from collections.abc import Callable
from functools import lru_cache

from winchat_api.config import Settings, get_settings
from winchat_api.retrieval.rerank.base import NoOpReranker, Reranker, RerankError
from winchat_api.retrieval.rerank.cohere_provider import CohereReranker
from winchat_api.retrieval.rerank.llm_provider import LLMReranker


def _build_cohere(settings: Settings, retry_budget_s: float) -> Reranker:
    return CohereReranker(
        api_key=settings.cohere_api_key or "",
        model=settings.rerank_model,
        timeout_s=settings.rerank_timeout_s,
        retry_budget_s=retry_budget_s,
    )


def _build_llm(settings: Settings, retry_budget_s: float) -> Reranker:
    # Imported here rather than at module scope: the LLM registry imports config, and a
    # top-level import would make these two registries import each other.
    from winchat_api.llm.registry import build_chat_provider

    return LLMReranker(llm=build_chat_provider(model=settings.rerank_llm_model))


def _build_none(settings: Settings, retry_budget_s: float) -> Reranker:
    return NoOpReranker()


_BUILDERS: dict[str, Callable[[Settings, float], Reranker]] = {
    "cohere": _build_cohere,
    "llm": _build_llm,
    "none": _build_none,
}


def available_providers() -> list[str]:
    return sorted(_BUILDERS)


def build_reranker(settings: Settings, *, retry_budget_s: float | None = None) -> Reranker:
    """Build the configured reranker, optionally overriding how long it may wait on a 429.

    The override exists for offline harnesses. They issue rerank calls in a tight loop and trip
    a per-minute limit the request path never approaches, and a reranker that gives up falls
    back to unranked order, so without it a benchmark quietly measures a reranker that was
    barely running.
    """
    builder = _BUILDERS.get(settings.rerank_provider)
    if builder is None:
        raise RerankError(
            f"unknown RERANK_PROVIDER {settings.rerank_provider!r}; "
            f"available: {', '.join(available_providers())}"
        )
    try:
        return builder(settings, retry_budget_s or settings.rerank_retry_budget_s)
    except RerankError:
        return NoOpReranker()


@lru_cache
def get_reranker() -> Reranker:
    """The configured reranker, on the request path.

    Falls back to the no-op when Cohere is selected but unkeyed, so a missing optional key
    degrades quality instead of taking the app down. The fallback is visible in every response,
    never silent.
    """
    return build_reranker(get_settings())
