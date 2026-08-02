"""Refusal-gate tests."""

import pytest

from winchat_api.chat.prompts import NO_CONTEXT_MESSAGE
from winchat_api.chat.refusal import should_refuse
from winchat_api.chat.service import AnswerPlan, stream_answer
from winchat_api.config import get_settings
from winchat_api.retrieval.models import RetrievedChunk
from winchat_api.retrieval.service import RetrievalResult


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _result(best_dense: float, *, rerank: float | None = None) -> RetrievalResult:
    scores: dict[str, float] = {"dense": best_dense}
    if rerank is not None:
        scores["rerank"] = rerank
    chunk = RetrievedChunk(
        chunk_id=1, a_id="1", question="Q", content="C", url="https://x.test", scores=scores
    )
    return RetrievalResult(query="q", chunks=[chunk], best_dense_score=best_dense)


def test_a_close_match_is_answered():
    """0.7329 was the weakest on-topic query during calibration."""
    assert should_refuse(_result(0.7329)) is None


def test_a_distant_match_is_refused():
    """0.5609 was "how do I bake sourdough bread" against this corpus."""
    refusal = should_refuse(_result(0.5609))

    assert refusal is not None
    assert refusal.stage == "dense"
    assert refusal.score == 0.5609


def test_empty_retrieval_is_refused():
    assert should_refuse(RetrievalResult(query="q")) is not None


def test_the_threshold_boundary_is_inclusive():
    """Exactly at the threshold answers; the gate is "below", not "at or below"."""
    assert should_refuse(_result(0.70)) is None
    assert should_refuse(_result(0.6999)) is not None


def test_the_rerank_gate_is_off_until_it_is_calibrated():
    """An uncalibrated threshold is worse than none, so a low rerank score alone passes."""
    assert should_refuse(_result(0.80, rerank=0.01)) is None


def test_the_rerank_gate_refuses_once_enabled(monkeypatch):
    monkeypatch.setenv("REFUSAL_MIN_RERANK_SCORE", "0.3")
    get_settings.cache_clear()

    refusal = should_refuse(_result(0.80, rerank=0.01))

    assert refusal is not None
    assert refusal.stage == "rerank"


def test_the_dense_threshold_is_configurable(monkeypatch):
    """It is model- and corpus-specific, so it must be tunable without a code change."""
    monkeypatch.setenv("REFUSAL_MIN_DENSE_SCORE", "0.5")
    get_settings.cache_clear()

    assert should_refuse(_result(0.5609)) is None


async def test_a_refused_plan_never_calls_the_model():
    """Refusing must cost zero tokens — that is half the point of the cheap gate."""

    class ExplodingLLM:
        name = "boom"
        model = "boom"

        def stream(self, *args, **kwargs):
            raise AssertionError("the model must not be called when refusing")

    plan = AnswerPlan(
        question="q",
        search_query="q",
        refusal=should_refuse(RetrievalResult(query="q")),
    )

    chunks = [token async for token in stream_answer(ExplodingLLM(), plan)]

    assert chunks == [NO_CONTEXT_MESSAGE]
