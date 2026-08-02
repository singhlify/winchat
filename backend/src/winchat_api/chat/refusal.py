"""Deciding when not to answer.

Two independent defences, because neither is sufficient alone:

1. **A retrieval threshold** (here). If nothing retrieved is topically close, the model is
   never called. This is the cheap, deterministic gate — no tokens spent, no latency, and
   no opportunity to hallucinate from irrelevant context.
2. **A grounding instruction in the prompt** (`prompts.SYSTEM_PROMPT`, rule 3). This
   catches what a similarity score structurally cannot.

Why both: calibrating on real queries showed "What are the admission requirements at the
University of Toronto?" scoring 0.7849 against this corpus — above any usable threshold,
because the question genuinely is near-identical in meaning to "What are your admission
requirements?". Only a reader can notice it is about a different university. A threshold
alone would answer it with UWindsor's requirements and sound confident doing so.
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
