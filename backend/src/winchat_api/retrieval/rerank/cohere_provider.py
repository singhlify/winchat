"""Cohere Rerank.

Chosen over other cross-encoders partly for a Canadian-market reason: Cohere is a Toronto
company and its Command/Embed/Rerank line maps one-to-one onto a RAG pipeline, so
familiarity with it is a small local edge. Called over plain HTTP rather than the SDK — one
endpoint, one payload, and it keeps the dependency list honest.
"""

from collections.abc import Sequence

import httpx

from winchat_api.retrieval.models import RetrievedChunk
from winchat_api.retrieval.rerank.base import Reranker, RerankError


class CohereReranker(Reranker):
    name = "cohere"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_s: float = 15.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise RerankError("COHERE_API_KEY is not set")
        self.model = model
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
        try:
            response = await self._client.post(
                "/v2/rerank",
                json={
                    "model": self.model,
                    "query": query,
                    "documents": documents,
                    "top_n": min(top_n, len(documents)),
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RerankError(
                f"cohere: {exc.response.status_code} {exc.response.text[:200]}"
            ) from exc
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
