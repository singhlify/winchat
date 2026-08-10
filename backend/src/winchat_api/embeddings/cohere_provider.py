"""Embeddings from Cohere's hosted `/v2/embed` endpoint. Used in deployment because an
in-process model does not fit the container size limit.
"""

import asyncio
import logging
import random
from collections.abc import Sequence

import httpx

from winchat_api.embeddings.base import EmbeddingError, EmbeddingProvider

logger = logging.getLogger(__name__)

MAX_BATCH = 96


class CohereEmbeddingProvider(EmbeddingProvider):
    name = "cohere"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "embed-v4.0",
        dimension: int = 1024,
        timeout_s: float = 30.0,
        retry_budget_s: float = 20.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise EmbeddingError("COHERE_API_KEY is not set")

        self.model = model
        self.dimension = dimension
        # Provider AND model AND width. All three change the space; the pipeline compares
        # this string to decide whether the corpus needs re-embedding.
        self.model_id = f"cohere/{model}/{dimension}"
        self._retry_budget_s = retry_budget_s
        self._client = client or httpx.AsyncClient(
            base_url="https://api.cohere.com",
            timeout=timeout_s,
            headers={"authorization": f"Bearer {api_key}"},
        )

    async def _post(self, payload: dict) -> list[list[float]]:
        """One embed call, retried within a time budget while the server says 429."""
        deadline = asyncio.get_running_loop().time() + self._retry_budget_s
        attempt = 0

        while True:
            attempt += 1
            try:
                response = await self._client.post("/v2/embed", json=payload)
                response.raise_for_status()
                break
            except httpx.HTTPStatusError as exc:
                retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
                # Capped near the length of the rate-limit window itself: the limit is per
                # minute, so backing off much longer than that just wastes the budget.
                delay = min(2.0**attempt, 15.0) + random.uniform(0.1, 0.6)
                if not retryable or asyncio.get_running_loop().time() + delay > deadline:
                    raise EmbeddingError(
                        f"cohere: {exc.response.status_code} {exc.response.text[:200]}"
                    ) from exc
                logger.info("cohere embed rate-limited, waiting %.1fs", delay)
                await asyncio.sleep(delay)
            except httpx.HTTPError as exc:
                raise EmbeddingError(f"cohere: {exc}") from exc

        # v2 returns embeddings keyed by type, not as a bare list.
        vectors = response.json().get("embeddings", {}).get("float")
        if not vectors:
            raise EmbeddingError("cohere: response contained no float embeddings")
        return [[float(value) for value in vector] for vector in vectors]

    def _payload(self, texts: Sequence[str], input_type: str) -> dict:
        return {
            "model": self.model,
            "texts": list(texts),
            "input_type": input_type,
            "embedding_types": ["float"],
            "output_dimension": self.dimension,
            # A chunk longer than the context window is truncated rather than rejected.
            # Losing the tail of one long chunk beats failing an entire ingest run.
            "truncate": "END",
        }

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []
        for start in range(0, len(texts), MAX_BATCH):
            batch = texts[start : start + MAX_BATCH]
            vectors.extend(await self._post(self._payload(batch, "search_document")))

        if len(vectors) != len(texts):
            raise EmbeddingError(f"cohere: asked for {len(texts)} vectors, got {len(vectors)}")
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self._post(self._payload([text], "search_query"))
        return vectors[0]

    async def aclose(self) -> None:
        await self._client.aclose()
