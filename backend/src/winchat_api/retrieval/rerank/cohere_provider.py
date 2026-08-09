"""Cohere Rerank.

Chosen over other cross-encoders partly for a Canadian-market reason: Cohere is a Toronto
company and its Command/Embed/Rerank line maps one-to-one onto a RAG pipeline, so familiarity
with it is a small local edge. Called over plain HTTP rather than the SDK, one endpoint, one
payload, and it keeps the dependency list honest.
"""

import asyncio
import logging
import random
from collections.abc import Sequence

import httpx

from winchat_api.retrieval.models import RetrievedChunk
from winchat_api.retrieval.rerank.base import Reranker, RerankError

logger = logging.getLogger(__name__)


class CohereReranker(Reranker):
    name = "cohere"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_s: float = 15.0,
        retry_budget_s: float = 8.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise RerankError("COHERE_API_KEY is not set")
        self.model = model
        self._retry_budget_s = retry_budget_s
        self._client = client or httpx.AsyncClient(
            base_url="https://api.cohere.com",
            timeout=timeout_s,
            headers={"authorization": f"Bearer {api_key}"},
        )

    async def rerank(
        self, query: str, chunks: Sequence[RetrievedChunk], *, top_n: int
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []

        # Rerank the contextualized passage: the parent question is often the strongest
        # signal that a chunk answers the query.
        documents = [f"{chunk.question}\n\n{chunk.content}" for chunk in chunks]
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_n": min(top_n, len(documents)),
        }

        # Trial keys are capped at 10 calls/minute, and without a retry a burst of questions
        # silently degraded to unranked order, which is how a working reranker can look like
        # it does nothing. The budget is small on purpose: this sits in the request path, so
        # waiting a few seconds is worth it and waiting a minute is not.
        deadline = asyncio.get_running_loop().time() + self._retry_budget_s
        attempt = 0

        while True:
            attempt += 1
            try:
                response = await self._client.post("/v2/rerank", json=payload)
                response.raise_for_status()
                break
            except httpx.HTTPStatusError as exc:
                retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
                delay = min(2.0**attempt, 5.0) + random.uniform(0.1, 0.6)
                if not retryable or asyncio.get_running_loop().time() + delay > deadline:
                    raise RerankError(
                        f"cohere: {exc.response.status_code} {exc.response.text[:200]}"
                    ) from exc
                logger.info("cohere rerank rate-limited, waiting %.1fs", delay)
                await asyncio.sleep(delay)
            except httpx.HTTPError as exc:
                raise RerankError(f"cohere: {exc}") from exc

        results = response.json().get("results", [])
        reranked: list[RetrievedChunk] = []
        for result in results:
            chunk = chunks[result["index"]]
            chunk.scores["rerank"] = float(result["relevance_score"])
            reranked.append(chunk)
        return reranked

    async def aclose(self) -> None:
        await self._client.aclose()
