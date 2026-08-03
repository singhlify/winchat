"""Embedding provider selection.

Mirrors `llm/registry.py`. Ollama is the default: open weights, runs locally, no vendor
call. A hosted open-weight backend gets added here at deploy time — and because ingestion
stamps every vector with `model_id`, swapping the model is a re-ingest, not a silent
mismatch.
"""

from collections.abc import Callable
from functools import lru_cache

from winchat_api.config import Settings, get_settings
from winchat_api.embeddings.base import EmbeddingError, EmbeddingProvider
from winchat_api.embeddings.fastembed_provider import FastEmbedProvider
from winchat_api.embeddings.ollama_provider import OllamaEmbeddingProvider
from winchat_api.embeddings.openai_compatible import OpenAICompatibleEmbeddingProvider


def _build_ollama(settings: Settings) -> EmbeddingProvider:
    return OllamaEmbeddingProvider(
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
        timeout_s=settings.embedding_timeout_s,
    )


def _build_openai_compatible(settings: Settings) -> EmbeddingProvider:
    return OpenAICompatibleEmbeddingProvider(
        base_url=settings.embedding_base_url or "",
        api_key=settings.embedding_api_key or "",
        model=settings.embedding_model,
        timeout_s=settings.embedding_timeout_s,
    )


def _build_fastembed(settings: Settings) -> EmbeddingProvider:
    return FastEmbedProvider(model=settings.fastembed_model, cache_dir=settings.fastembed_cache_dir)


_BUILDERS: dict[str, Callable[[Settings], EmbeddingProvider]] = {
    "ollama": _build_ollama,
    "fastembed": _build_fastembed,
    "openai_compatible": _build_openai_compatible,
}


def available_providers() -> list[str]:
    return sorted(_BUILDERS)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    builder = _BUILDERS.get(settings.embedding_provider)
    if builder is None:
        raise EmbeddingError(
            f"unknown EMBEDDING_PROVIDER {settings.embedding_provider!r}; "
            f"available: {', '.join(available_providers())}"
        )
    return builder(settings)
