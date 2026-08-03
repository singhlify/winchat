"""Embeddings computed in-process with ONNX.

The deployment answer. Ollama needs a separate daemon holding the model in memory, which
does not fit a small instance; `sentence-transformers` drags in ~2.5 GB of torch. fastembed
runs the same nomic weights through onnxruntime in about 53 MB, inside the API process —
no daemon, no vendor, no API key, and no network hop on the request path.

Two things this module must get right:

**The prefixes are fastembed's job here, not ours.** `query_embed` and `embed` apply
nomic's `search_query:` / `search_document:` prefixes internally, so unlike the Ollama
provider we must NOT add them — doing so would double them and shift every vector.

**It is CPU-bound and synchronous.** Running it directly in an async handler would block
the event loop and stall every other in-flight request, including active SSE streams. Every
call goes through a worker thread.

Vectors from this provider are NOT interchangeable with Ollama's, despite the same model
name and 768 dimensions. Measured: cosine 0.60-0.91 between the two for identical text, and
zero top-5 overlap on two of three test queries. Different quantisation, different space.
`model_id` therefore names the runtime as well as the model, so the ingestion pipeline sees
a change and re-embeds the corpus instead of silently mixing spaces.
"""

import asyncio
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from winchat_api.embeddings.base import EmbeddingError, EmbeddingProvider


@lru_cache(maxsize=4)
def _load(model_name: str, cache_dir: str | None) -> Any:
    """Load once per process. The model is a few hundred MB in memory."""
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise EmbeddingError("fastembed is not installed") from exc

    try:
        return TextEmbedding(model_name=model_name, cache_dir=cache_dir)
    except Exception as exc:
        raise EmbeddingError(f"fastembed: could not load {model_name} ({exc})") from exc


class FastEmbedProvider(EmbeddingProvider):
    name = "fastembed"

    def __init__(
        self,
        *,
        model: str = "nomic-ai/nomic-embed-text-v1.5",
        cache_dir: str | None = None,
    ) -> None:
        self._model_name = model
        self._cache_dir = cache_dir
        # Stamped onto every stored vector. The runtime is part of the identity because the
        # same weights under a different runtime produce a different space.
        self.model_id = f"fastembed/{model}"

    def _embedder(self) -> Any:
        return _load(self._model_name, self._cache_dir)

    async def warm(self) -> None:
        """Load the model ahead of the first request.

        Worth doing at startup on a scale-to-zero host: otherwise the first user after a
        cold start pays the model load on top of their query.
        """
        await asyncio.to_thread(self._embedder)

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        def run() -> list[list[float]]:
            # `embed` applies nomic's search_document prefix itself.
            return [vector.tolist() for vector in self._embedder().embed(list(texts))]

        try:
            return await asyncio.to_thread(run)
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(f"fastembed: {exc}") from exc

    async def embed_query(self, text: str) -> list[float]:
        def run() -> list[float]:
            # `query_embed` applies the search_query prefix itself.
            return next(iter(self._embedder().query_embed([text]))).tolist()

        try:
            return await asyncio.to_thread(run)
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(f"fastembed: {exc}") from exc
