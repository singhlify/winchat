"""Turns retrieved chunks into a numbered context block. Chunks are grouped by `a_id`, so
one article is one citation.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from winchat_api.retrieval.models import RetrievedChunk


@dataclass(frozen=True, slots=True)
class Citation:
    index: int  # the [n] the model writes
    a_id: str
    question: str
    url: str
    score: float


@dataclass(frozen=True, slots=True)
class BuiltContext:
    text: str
    citations: list[Citation]


def build_context(chunks: Sequence[RetrievedChunk]) -> BuiltContext:
    by_answer: dict[str, list[RetrievedChunk]] = {}
    for chunk in chunks:
        by_answer.setdefault(chunk.a_id, []).append(chunk)

    citations: list[Citation] = []
    blocks: list[str] = []

    for index, (a_id, group) in enumerate(by_answer.items(), start=1):
        best = max(group, key=lambda chunk: chunk.rank_score)
        citations.append(
            Citation(
                index=index,
                a_id=a_id,
                question=best.question,
                url=best.url,
                score=round(best.rank_score, 4),
            )
        )
        body = "\n\n".join(chunk.content for chunk in group)
        blocks.append(f"[{index}] {best.question}\n{body}")

    return BuiltContext(text="\n\n---\n\n".join(blocks), citations=citations)
