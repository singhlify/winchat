"""The reranker interface. A cross-encoder reads the query and passage together, which is
more accurate than comparing vectors but too slow for the whole corpus, so it runs over the
fused candidates only.
"""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from winchat_api.retrieval.models import RetrievedChunk


@runtime_checkable
class Reranker(Protocol):
    name: str
    model: str

    async def rerank(
        self, query: str, chunks: Sequence[RetrievedChunk], *, top_n: int
    ) -> list[RetrievedChunk]:
        """Return the best `top_n` chunks, best first, with a `rerank` score attached."""
        ...


class RerankError(RuntimeError):
    """A rerank call failed."""


class NoOpReranker(Reranker):
    """Used when no reranker is configured: truncate, do not reorder.

    Deliberately not silent. The retrieval result records that reranking was skipped, so
    a quality comparison can never accidentally credit a reranker that never ran.
    """

    name = "none"
    model = "none"

    async def rerank(
        self, query: str, chunks: Sequence[RetrievedChunk], *, top_n: int
    ) -> list[RetrievedChunk]:
        return list(chunks[:top_n])
