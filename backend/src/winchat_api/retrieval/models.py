"""Shared retrieval types."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class RetrievedChunk:
    """One candidate passage and how it was found. `scores` keeps each stage's number rather than
    collapsing to one, so a stage that drops the right chunk can be identified.
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
