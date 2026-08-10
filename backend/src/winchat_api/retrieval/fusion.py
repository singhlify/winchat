"""Reciprocal Rank Fusion over the dense and lexical result lists.

RRF scores by rank rather than by raw score. Cosine similarity and `ts_rank_cd` are on
different scales, so combining the scores directly would require a calibration between them
that does not exist.
"""

from collections.abc import Sequence

from winchat_api.retrieval.models import RetrievedChunk

DEFAULT_RRF_K = 60


def reciprocal_rank_fusion(
    result_lists: Sequence[Sequence[RetrievedChunk]], *, k: int = DEFAULT_RRF_K
) -> list[RetrievedChunk]:
    """Fuse ranked lists into one, best first. Per-stage scores are preserved."""
    merged: dict[int, RetrievedChunk] = {}
    fused_scores: dict[int, float] = {}

    for results in result_lists:
        for rank, chunk in enumerate(results, start=1):
            existing = merged.get(chunk.chunk_id)
            if existing is None:
                merged[chunk.chunk_id] = chunk
            else:
                # Same chunk found by the other arm. Keep both stages' opinions.
                existing.scores.update(chunk.scores)
            fused_scores[chunk.chunk_id] = fused_scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank)

    for chunk_id, score in fused_scores.items():
        merged[chunk_id].scores["rrf"] = score

    return sorted(merged.values(), key=lambda chunk: fused_scores[chunk.chunk_id], reverse=True)


def best_per_answer(chunks: Sequence[RetrievedChunk]) -> list[RetrievedChunk]:
    """Keep only the highest-ranked chunk of each source answer, preserving order.

    Measured need, not tidiness. Several golden cases failed with the correct answer at dense
    rank 1 but fused rank 8, because the six final slots were being spent on two or three
    distinct answers, the same FAQ article occupying three of them.
    """
    seen: set[str] = set()
    unique: list[RetrievedChunk] = []
    for chunk in chunks:
        if chunk.a_id in seen:
            continue
        seen.add(chunk.a_id)
        unique.append(chunk)
    return unique
