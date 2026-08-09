"""Fusion and context-building tests. Pure logic, no database, no network."""

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


# ----------------------------------------------------------------- llm reranker


class _StubJudgeLLM:
    """Returns a canned ordering; records the prompt it was given."""

    name = "stub"
    model = "stub"

    def __init__(self, payload: str):
        self.payload = payload
        self.prompt = ""

    async def complete(self, messages, **kwargs):
        from winchat_api.llm.base import Completion

        self.prompt = messages[-1].content
        assert kwargs.get("json_object") is True
        return Completion(text=self.payload, model="stub", provider="stub")


async def test_llm_rerank_reorders_by_the_returned_ranking():
    from winchat_api.retrieval.rerank.llm_provider import LLMReranker

    chunks = [_chunk(1, a_id="a"), _chunk(2, a_id="b"), _chunk(3, a_id="c")]
    reranker = LLMReranker(llm=_StubJudgeLLM('{"ranked": [3, 1]}'))

    result = await reranker.rerank("q", chunks, top_n=6)

    assert [chunk.a_id for chunk in result] == ["c", "a"]
    assert result[0].scores["rerank"] > result[1].scores["rerank"]


async def test_llm_rerank_ignores_out_of_range_and_duplicate_indexes():
    """A hallucinated index must be dropped, never wrapped around into a wrong passage."""
    from winchat_api.retrieval.rerank.llm_provider import LLMReranker

    chunks = [_chunk(1, a_id="a"), _chunk(2, a_id="b")]
    reranker = LLMReranker(llm=_StubJudgeLLM('{"ranked": [99, 2, 2, -1, "x"]}'))

    result = await reranker.rerank("q", chunks, top_n=6)

    assert [chunk.a_id for chunk in result] == ["b"]


async def test_llm_rerank_keeping_nothing_is_a_verdict_not_a_fallback():
    """Empty means "none of these are relevant". The refusal gate must see that."""
    from winchat_api.retrieval.rerank.llm_provider import LLMReranker

    reranker = LLMReranker(llm=_StubJudgeLLM('{"ranked": []}'))

    assert await reranker.rerank("q", [_chunk(1)], top_n=6) == []


async def test_llm_rerank_surfaces_unparseable_output_as_a_rerank_error():
    """The service layer catches RerankError and degrades to fused order, visibly."""
    import pytest

    from winchat_api.retrieval.rerank.base import RerankError
    from winchat_api.retrieval.rerank.llm_provider import LLMReranker

    reranker = LLMReranker(llm=_StubJudgeLLM("not json"))

    with pytest.raises(RerankError):
        await reranker.rerank("q", [_chunk(1)], top_n=6)
