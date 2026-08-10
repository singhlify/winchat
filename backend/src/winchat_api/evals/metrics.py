"""Tier 1: deterministic checks. No model call, so they cannot flake."""

import re
from dataclasses import dataclass, field

from winchat_api.chat.context import Citation
from winchat_api.evals.dataset import GoldenCase
from winchat_api.retrieval.service import RetrievalResult


@dataclass
class DeterministicResult:
    case_id: str
    passed: bool = True
    failures: list[str] = field(default_factory=list)
    retrieval_hit: bool | None = None  # None when the case does not score retrieval
    retrieval_rank: int | None = None  # 1-based rank of the first expected a_id

    def fail(self, reason: str) -> None:
        self.passed = False
        self.failures.append(reason)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).lower()


def check_case(
    case: GoldenCase,
    *,
    answer: str,
    citations: list[Citation],
    retrieval: RetrievalResult | None,
    refused: bool,
) -> DeterministicResult:
    result = DeterministicResult(case_id=case.id)
    normalized = _normalize(answer)

    if case.expect_refusal and not refused:
        result.fail("expected a refusal, got an answer")
    if not case.expect_refusal and refused and case.category != "adversarial":
        result.fail("refused a question it should have answered")

    for needle in case.must_include:
        if _normalize(needle) not in normalized:
            result.fail(f"missing required content: {needle!r}")

    for needle in case.must_not_include:
        if _normalize(needle) in normalized:
            result.fail(f"contains forbidden content: {needle!r}")

    if case.must_not_match and re.search(case.must_not_match, answer, re.IGNORECASE):
        result.fail(f"matched forbidden pattern: {case.must_not_match}")

    # Every [n] the model wrote must resolve to a source it was actually given. A dangling
    # citation is a fabricated reference wearing a citation's clothes.
    valid = {citation.index for citation in citations}
    for marker in {int(m) for m in re.findall(r"\[(\d+)\]", answer)}:
        if marker not in valid:
            result.fail(f"cited [{marker}] but no such source was provided")

    if case.is_scored_for_retrieval and retrieval is not None:
        expected = set(case.expected_a_ids)
        ranked = [chunk.a_id for chunk in retrieval.chunks]
        result.retrieval_hit = any(a_id in expected for a_id in ranked)
        result.retrieval_rank = next(
            (rank for rank, a_id in enumerate(ranked, start=1) if a_id in expected), None
        )
        if not result.retrieval_hit:
            result.fail(f"none of {sorted(expected)} reached the model")

    return result


def recall(results: list[DeterministicResult]) -> float:
    """Share of retrieval-scored cases whose expected source reached the model."""
    scored = [r for r in results if r.retrieval_hit is not None]
    if not scored:
        return 0.0
    return sum(1 for r in scored if r.retrieval_hit) / len(scored)


def mean_reciprocal_rank(results: list[DeterministicResult]) -> float:
    """Mean reciprocal rank. Recall alone hides a change that pushes the right answer from rank 1
    to rank 6.
    """
    scored = [r for r in results if r.retrieval_hit is not None]
    if not scored:
        return 0.0
    return sum(1 / r.retrieval_rank if r.retrieval_rank else 0.0 for r in scored) / len(scored)


def refusal_accuracy(results: list[DeterministicResult], cases: list[GoldenCase]) -> float:
    """Share of refusal cases handled correctly (both directions)."""
    by_id = {case.id: case for case in cases}
    relevant = [r for r in results if by_id[r.case_id].expect_refusal]
    if not relevant:
        return 1.0
    correct = sum(1 for r in relevant if not any("refus" in failure for failure in r.failures))
    return correct / len(relevant)
