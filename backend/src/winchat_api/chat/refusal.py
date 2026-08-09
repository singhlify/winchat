"""Deciding when not to answer.

Two independent defences, because neither is sufficient alone: a retrieval threshold here, and
rule 3 of the system prompt telling the model to refuse when the sources do not answer.
"""

from dataclasses import dataclass

from winchat_api.config import get_settings
from winchat_api.retrieval.service import RetrievalResult


@dataclass(frozen=True, slots=True)
class Refusal:
    reason: str
    score: float
    threshold: float
    stage: str


def should_refuse(retrieval: RetrievalResult) -> Refusal | None:
    """Return a Refusal when retrieval did not find anything worth answering from."""
    settings = get_settings()

    if not retrieval.chunks:
        return Refusal(
            reason="retrieval returned no passages", score=0.0, threshold=0.0, stage="empty"
        )

    if retrieval.best_dense_score < settings.refusal_min_dense_score:
        return Refusal(
            reason="no passage was close enough to the question",
            score=round(retrieval.best_dense_score, 4),
            threshold=settings.refusal_min_dense_score,
            stage="dense",
        )

    floor = settings.refusal_min_rerank_score
    if floor is not None and "rerank" in retrieval.chunks[0].scores:
        top = retrieval.chunks[0].scores["rerank"]
        if top < floor:
            return Refusal(
                reason="the reranker judged every passage irrelevant",
                score=round(top, 4),
                threshold=floor,
                stage="rerank",
            )

    return None
