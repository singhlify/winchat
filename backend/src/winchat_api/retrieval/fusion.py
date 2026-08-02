"""Reciprocal Rank Fusion — merging the dense and lexical result lists.

RRF scores a document by `sum(1 / (k + rank))` over the lists it appears in. It uses
*ranks*, never raw scores, which is precisely why it works here: cosine similarity
(0-1, tightly clustered near the top) and `ts_rank_cd` (unbounded, corpus-dependent) are
not on comparable scales, and any attempt to normalize them into a weighted sum invents a
calibration that does not exist.

`k=60` is the value from the original RRF paper and the common default. The research pass
explicitly refuted a 0.6/0.4 dense-to-lexical weighting as unsupported, so no weights are
applied — a document found by both arms wins on the strength of appearing in both.
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
                # Same chunk found by the other arm — keep both stages' opinions.
                existing.scores.update(chunk.scores)
            fused_scores[chunk.chunk_id] = fused_scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank)

    for chunk_id, score in fused_scores.items():
        merged[chunk_id].scores["rrf"] = score

    return sorted(merged.values(), key=lambda chunk: fused_scores[chunk.chunk_id], reverse=True)
