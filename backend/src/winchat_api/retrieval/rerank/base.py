"""The provider-agnostic reranker interface.

A reranker is a cross-encoder: instead of comparing two independent vectors, it reads the
query and the passage *together* and scores the pair. That is far more accurate and far
too slow to run over the whole corpus — which is exactly why it sits after retrieval, over
a few dozen candidates.

Reranking is a precision tool, not a recall tool: it can only reorder what retrieval
already fetched. It is worth its ~200ms when the right answer is reliably inside the top
50 but not the top 5.
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

    Deliberately not silent — the retrieval result records that reranking was skipped, so
    a quality comparison can never accidentally credit a reranker that never ran.
    """

    name = "none"
    model = "none"

    async def rerank(
        self, query: str, chunks: Sequence[RetrievedChunk], *, top_n: int
    ) -> list[RetrievedChunk]:
        return list(chunks[:top_n])
