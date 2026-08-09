"""Shared retrieval types."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class RetrievedChunk:
    """One candidate passage, plus how it was found.

    `scores` keeps every stage's number (dense, lexical, rrf, rerank) rather than collapsing to
    one. Retrieval bugs are otherwise invisible: "the right chunk was ranked 4th by dense and
    1st by lexical, and the reranker dropped it" is only diagnosable if each stage's opinion
    survives.
    """

    chunk_id: int
    a_id: str
    question: str
    content: str
    url: str
    scores: dict[str, float] = field(default_factory=dict)

    @property
    def rank_score(self) -> float:
        """The score that decides final order, the latest stage to express an opinion."""
        for stage in ("rerank", "rrf", "dense", "lexical"):
            if stage in self.scores:
                return self.scores[stage]
        return 0.0
