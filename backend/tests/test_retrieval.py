"""Fusion and context-building tests. Pure logic — no database, no network."""

from winchat_api.chat.context import build_context
from winchat_api.retrieval.fusion import reciprocal_rank_fusion
from winchat_api.retrieval.models import RetrievedChunk


def _chunk(chunk_id: int, a_id: str = "a", stage: str = "dense", score: float = 1.0):
    return RetrievedChunk(
        chunk_id=chunk_id,
        a_id=a_id,
        question=f"Question {a_id}",
        content=f"Content {chunk_id}",
        url=f"https://example.test/{a_id}",
        scores={stage: score},
    )


def test_a_chunk_found_by_both_arms_outranks_one_found_by_either():
    """The whole point of fusion: agreement between independent retrievers is evidence."""
    dense = [_chunk(1), _chunk(2), _chunk(3)]
    lexical = [_chunk(3, stage="lexical"), _chunk(4, stage="lexical")]

    fused = reciprocal_rank_fusion([dense, lexical])

    assert fused[0].chunk_id == 3


def test_fusion_keeps_every_stage_score():
    """A retrieval bug is undiagnosable if the stages' opinions are collapsed into one."""
    fused = reciprocal_rank_fusion(
        [[_chunk(1, stage="dense", score=0.8)], [_chunk(1, stage="lexical", score=2.5)]]
    )

    assert fused[0].scores["dense"] == 0.8
    assert fused[0].scores["lexical"] == 2.5
    assert "rrf" in fused[0].scores


def test_fusion_deduplicates_by_chunk_id():
    fused = reciprocal_rank_fusion([[_chunk(1), _chunk(2)], [_chunk(1, stage="lexical")]])

    assert [chunk.chunk_id for chunk in fused] == [1, 2]


def test_fusion_uses_rank_not_score():
    """Cosine similarity and ts_rank_cd are not on comparable scales; only order is used."""
    dense = [_chunk(1, score=0.99), _chunk(2, score=0.98)]
    lexical = [_chunk(2, stage="lexical", score=1000.0)]

    fused = reciprocal_rank_fusion([dense, lexical])

    # Chunk 2 wins by appearing in both lists, not because its lexical score was huge.
    assert fused[0].chunk_id == 2
    assert fused[0].scores["rrf"] < 1.0


def test_fusion_of_nothing_is_empty():
    assert reciprocal_rank_fusion([[], []]) == []


def test_chunks_from_one_answer_share_a_citation_number():
    """Two chunks of one FAQ answer are one source; numbering them twice fakes agreement."""
    chunks = [_chunk(1, a_id="246"), _chunk(2, a_id="246"), _chunk(3, a_id="900")]

    context = build_context(chunks)

    assert [citation.index for citation in context.citations] == [1, 2]
    assert [citation.a_id for citation in context.citations] == ["246", "900"]


def test_both_chunks_of_a_grouped_answer_reach_the_model():
    context = build_context([_chunk(1, a_id="246"), _chunk(2, a_id="246")])

    assert "Content 1" in context.text
    assert "Content 2" in context.text


def test_urls_are_never_placed_in_the_prompt():
    """A model that cannot see a URL cannot invent one; the UI resolves [n] to a link."""
    context = build_context([_chunk(1, a_id="246")])

    assert "https://" not in context.text
    assert context.citations[0].url.startswith("https://")


def test_context_numbering_starts_at_one():
    context = build_context([_chunk(1, a_id="x")])

    assert context.citations[0].index == 1
    assert context.text.startswith("[1] ")


def test_empty_retrieval_builds_empty_context():
    context = build_context([])

    assert context.text == ""
    assert context.citations == []
