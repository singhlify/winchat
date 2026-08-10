"""Embedding provider selection, keyed by EMBEDDING_PROVIDER."""

from collections.abc import Callable
from functools import lru_cache

from winchat_api.config import Settings, get_settings
from winchat_api.embeddings.base import EmbeddingError, EmbeddingProvider
from winchat_api.embeddings.cohere_provider import CohereEmbeddingProvider
from winchat_api.embeddings.fastembed_provider import FastEmbedProvider
from winchat_api.embeddings.ollama_provider import OllamaEmbeddingProvider
from winchat_api.embeddings.openai_compatible import OpenAICompatibleEmbeddingProvider


def _build_ollama(settings: Settings, retry_budget_s: float) -> EmbeddingProvider:
    return OllamaEmbeddingProvider(
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
        timeout_s=settings.embedding_timeout_s,
    )


def _build_openai_compatible(settings: Settings, retry_budget_s: float) -> EmbeddingProvider:
    return OpenAICompatibleEmbeddingProvider(
        base_url=settings.embedding_base_url or "",
        api_key=settings.embedding_api_key or "",
        model=settings.embedding_model,
        timeout_s=settings.embedding_timeout_s,
    )


def _build_fastembed(settings: Settings, retry_budget_s: float) -> EmbeddingProvider:
    return FastEmbedProvider(model=settings.fastembed_model, cache_dir=settings.fastembed_cache_dir)


def _build_cohere(settings: Settings, retry_budget_s: float) -> EmbeddingProvider:
    return CohereEmbeddingProvider(
        api_key=settings.cohere_api_key or "",
        model=settings.cohere_embed_model,
        dimension=settings.cohere_embed_dimension,
        timeout_s=settings.embedding_timeout_s,
        retry_budget_s=retry_budget_s,
    )


_BUILDERS: dict[str, Callable[[Settings, float], EmbeddingProvider]] = {
    "ollama": _build_ollama,
    "fastembed": _build_fastembed,
    "cohere": _build_cohere,
    "openai_compatible": _build_openai_compatible,
}


def available_providers() -> list[str]:
    return sorted(_BUILDERS)


def build_embedding_provider(
    settings: Settings, *, retry_budget_s: float | None = None
) -> EmbeddingProvider:
    builder = _BUILDERS.get(settings.embedding_provider)
    if builder is None:
        raise EmbeddingError(
            f"unknown EMBEDDING_PROVIDER {settings.embedding_provider!r}; "
            f"available: {', '.join(available_providers())}"
        )
    return builder(settings, retry_budget_s or settings.embedding_retry_budget_s)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    """The request-path provider. Cached so the whole process shares one client."""
    return build_embedding_provider(get_settings())
