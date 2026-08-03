"""Reranker selection — same shape as the LLM and embedding registries."""

from collections.abc import Callable
from functools import lru_cache

from winchat_api.config import Settings, get_settings
from winchat_api.retrieval.rerank.base import NoOpReranker, Reranker, RerankError
from winchat_api.retrieval.rerank.cohere_provider import CohereReranker
from winchat_api.retrieval.rerank.llm_provider import LLMReranker


def _build_cohere(settings: Settings) -> Reranker:
    return CohereReranker(
        api_key=settings.cohere_api_key or "",
        model=settings.rerank_model,
        timeout_s=settings.rerank_timeout_s,
        retry_budget_s=settings.rerank_retry_budget_s,
    )


def _build_llm(settings: Settings) -> Reranker:
    # Imported here rather than at module scope: the LLM registry imports config, and a
    # top-level import would make these two registries import each other.
    from winchat_api.llm.registry import build_chat_provider

    return LLMReranker(llm=build_chat_provider(model=settings.rerank_llm_model))


def _build_none(settings: Settings) -> Reranker:
    return NoOpReranker()


_BUILDERS: dict[str, Callable[[Settings], Reranker]] = {
    "cohere": _build_cohere,
    "llm": _build_llm,
    "none": _build_none,
}


def available_providers() -> list[str]:
    return sorted(_BUILDERS)


@lru_cache
def get_reranker() -> Reranker:
    """The configured reranker.

    Falls back to the no-op when Cohere is selected but unkeyed, so a missing optional key
    degrades quality instead of taking the app down. The fallback is visible in every
    response, never silent.

    It does NOT fall back to the LLM reranker, even though one is implemented. That stage
    only beats the baseline in a configuration whose token cost exceeds the free tier's
    per-minute budget, at which point it is rate-limited back into RRF order anyway; in the
    configuration that does fit, it measurably REDUCES recall (66.7% against an 83.3%
    baseline) because a small model over-filters. Same principle as the rerank refusal
    threshold: a stage that has not been shown to help is worse than no stage. Set
    RERANK_PROVIDER=llm to opt in.
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
