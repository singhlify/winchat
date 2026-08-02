"""The retrieval pipeline, end to end.

    query
      -> embed
      -> dense top-50  ┐
      -> lexical top-50┘ fused with RRF
      -> rerank -> top-n

The two arms run concurrently because neither depends on the other; the wall-clock cost of
hybrid retrieval is therefore the slower arm, not the sum.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field

import asyncpg

from winchat_api.config import get_settings
from winchat_api.embeddings.base import EmbeddingProvider
from winchat_api.retrieval.fusion import reciprocal_rank_fusion
from winchat_api.retrieval.models import RetrievedChunk
from winchat_api.retrieval.rerank.base import Reranker, RerankError
from winchat_api.retrieval.search import dense_search, lexical_search

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """What retrieval found, and how — the input to both generation and evaluation."""

    query: str
    chunks: list[RetrievedChunk] = field(default_factory=list)
    dense_count: int = 0
    lexical_count: int = 0
    fused_count: int = 0
    reranker: str = "none"
    rerank_skipped_reason: str | None = None
    latency_ms: dict[str, float] = field(default_factory=dict)

    @property
    def top_score(self) -> float:
        """Relevance of the best passage — what the Phase 4 refusal threshold reads."""
        return self.chunks[0].rank_score if self.chunks else 0.0


async def retrieve(
    *,
    pool: asyncpg.Pool,
    embedder: EmbeddingProvider,
    reranker: Reranker,
    query: str,
    dense_k: int | None = None,
    lexical_k: int | None = None,
    top_n: int | None = None,
) -> RetrievalResult:
    settings = get_settings()
    dense_k = dense_k if dense_k is not None else settings.retrieval_dense_k
    lexical_k = lexical_k if lexical_k is not None else settings.retrieval_lexical_k
    top_n = top_n if top_n is not None else settings.retrieval_top_n

    result = RetrievalResult(query=query)

    started = time.perf_counter()
    query_vector = await embedder.embed_query(query)
    result.latency_ms["embed"] = round((time.perf_counter() - started) * 1000, 1)

    started = time.perf_counter()
    dense, lexical = await asyncio.gather(
        dense_search(pool, query_vector, dense_k),
        lexical_search(pool, query, lexical_k),
    )
    result.latency_ms["search"] = round((time.perf_counter() - started) * 1000, 1)
    result.dense_count = len(dense)
    result.lexical_count = len(lexical)

    fused = reciprocal_rank_fusion([dense, lexical])
    result.fused_count = len(fused)

    started = time.perf_counter()
    try:
        result.chunks = await reranker.rerank(query, fused[: settings.rerank_pool], top_n=top_n)
        result.reranker = reranker.name
    except RerankError as exc:
        # A reranker outage must degrade quality, not break the answer. RRF order is a
        # perfectly serviceable fallback — and the reason is recorded, never swallowed.
        logger.warning("rerank failed, falling back to RRF order: %s", exc)
        result.chunks = fused[:top_n]
        result.reranker = "none"
        result.rerank_skipped_reason = str(exc)[:200]
    result.latency_ms["rerank"] = round((time.perf_counter() - started) * 1000, 1)

    if reranker.name == "none" and result.rerank_skipped_reason is None:
        result.rerank_skipped_reason = "no reranker configured"

    return result
