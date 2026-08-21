"""The spend ceiling for unmetered batch runs."""

import pytest

from winchat_api.provider_budget import (
    CallBudget,
    ProviderBudgetExceeded,
    current_budget,
    set_call_budget,
)
from winchat_api.retrieval.models import RetrievedChunk


def test_an_unset_budget_counts_but_never_refuses():
    """The API path relies on this: check_limits is its ceiling, not this counter."""
    budget = CallBudget(None)
    for _ in range(500):
        budget.spend("cohere.embed")

    assert budget.spent == 500


def test_the_ceiling_refuses_the_call_that_crosses_it():
    budget = CallBudget(2)
    budget.spend("cohere.embed")
    budget.spend("cohere.embed")

    with pytest.raises(ProviderBudgetExceeded, match="ceiling of 2"):
        budget.spend("cohere.embed")


def test_retries_count_because_a_retry_is_a_billable_call():
    """Cohere meters attempts, not logical operations, so the counter has to as well."""
    budget = set_call_budget(3)
    for _ in range(3):
        current_budget().spend("groq/qwen")

    assert budget.spent == 3
    with pytest.raises(ProviderBudgetExceeded):
        current_budget().spend("groq/qwen")


async def test_an_exhausted_budget_aborts_retrieval_instead_of_degrading(monkeypatch):
    """retrieve() falls back to fused order when the reranker fails. It must NOT do that here:
    silently unranked results would let a capped run finish and report success.
    """
    from winchat_api.retrieval import service

    chunk = RetrievedChunk(
        chunk_id=1, a_id="a", question="q", content="c", url="u", scores={"dense": 1.0}
    )

    async def fake_dense(pool, vector, limit):
        return [chunk]

    async def fake_lexical(pool, query, limit):
        return []

    class _BrokeReranker:
        name = "cohere"

        async def rerank(self, query, chunks, *, top_n):
            raise ProviderBudgetExceeded("cohere.rerank: over the ceiling")

    class _Embedder:
        async def embed_query(self, query):
            return [0.0]

    monkeypatch.setattr(service, "dense_search", fake_dense)
    monkeypatch.setattr(service, "lexical_search", fake_lexical)

    with pytest.raises(ProviderBudgetExceeded):
        await service.retrieve(
            pool=object(), embedder=_Embedder(), reranker=_BrokeReranker(), query="q"
        )
