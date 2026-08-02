"""Reranker selection — same shape as the LLM and embedding registries."""

from collections.abc import Callable
from functools import lru_cache

from winchat_api.config import Settings, get_settings
from winchat_api.retrieval.rerank.base import NoOpReranker, Reranker, RerankError
from winchat_api.retrieval.rerank.cohere_provider import CohereReranker


def _build_cohere(settings: Settings) -> Reranker:
    return CohereReranker(
        api_key=settings.cohere_api_key or "",
        model=settings.rerank_model,
        timeout_s=settings.rerank_timeout_s,
    )


def _build_none(settings: Settings) -> Reranker:
    return NoOpReranker()


_BUILDERS: dict[str, Callable[[Settings], Reranker]] = {
    "cohere": _build_cohere,
    "none": _build_none,
}


def available_providers() -> list[str]:
    return sorted(_BUILDERS)


@lru_cache
def get_reranker() -> Reranker:
    """The configured reranker.

    Falls back to the no-op when Cohere is selected but unkeyed, so a missing optional
    API key degrades retrieval quality instead of taking the whole app down. The fallback
    is visible in the retrieval result, never silent.
    """
    settings = get_settings()
    builder = _BUILDERS.get(settings.rerank_provider)
    if builder is None:
        raise RerankError(
            f"unknown RERANK_PROVIDER {settings.rerank_provider!r}; "
            f"available: {', '.join(available_providers())}"
        )
    try:
        return builder(settings)
    except RerankError:
        return NoOpReranker()
