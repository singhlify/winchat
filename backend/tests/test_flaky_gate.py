"""The pass-rate band for known failures that only fail some of the time.

Generation is not reproducible even at temperature 0.0, so scoring a flaky case on one
run measures the sample rather than the defect. These tests pin the behaviour that stops
a lucky run from reporting a defect as fixed, which is what happened to g004.
"""

import pytest

from winchat_api.evals.dataset import GoldenCase
from winchat_api.evals.metrics import DeterministicResult
from winchat_api.evals.run import (
    KNOWN_DETERMINISTIC_FAILURES,
    CaseOutcome,
    KnownFailure,
    _runs_for,
    build_report,
)


def _outcome(case_id: str, *, runs: int = 1, passes: int = 1) -> CaseOutcome:
    case = GoldenCase(id=case_id, question=f"q for {case_id}", category="answerable")
    result = DeterministicResult(case_id=case_id, passed=passes == runs)
    if passes < runs:
        result.failures.append("a check failed")
    return CaseOutcome(
        case=case,
        answer="an answer",
        refused=False,
        deterministic=result,
        runs=runs,
        passes=passes,
    )


def _report(outcomes):
    return build_report(outcomes, model="m", judge_model="none", reranker="r", duration=1.0)


def test_a_flaky_known_failure_inside_its_band_passes_the_gate():
    """g004 fails most of the time and passes some of it. That is the documented state."""
    report = _report([_outcome("g004", runs=10, passes=2), _outcome("g005", passes=0)])
    assert report.gates["deterministic"] is True
    assert report.out_of_band == {}
    assert report.observed_rates["g004"] == pytest.approx(0.2)


def test_a_known_failure_that_starts_always_passing_breaks_the_build():
    """The original invariant: a fixed defect must not leave the documentation stale."""
    report = _report([_outcome("g004", runs=10, passes=10), _outcome("g005", passes=0)])
    assert report.gates["deterministic"] is False
    assert "g004" in report.out_of_band
    assert "outside the declared" in report.out_of_band["g004"]


def test_one_lucky_run_cannot_report_a_flaky_defect_as_fixed():
    """The regression this whole mechanism exists for.

    g004 passes roughly 2 times in 10. A single run that happens to be one of those two
    used to empty `fixed_known_failures` and tell you to close the issue.
    """
    report = _report([_outcome("g004", runs=10, passes=1), _outcome("g005", passes=0)])
    assert report.gates["deterministic"] is True
    assert "g004" in report.deterministic_failed_ids


def test_a_flaky_case_that_gets_much_worse_also_breaks_the_build():
    """A band is an assertion in both directions, not just a ceiling."""
    declared = KnownFailure("drifts upward", runs=10, min_rate=0.3, max_rate=0.6)
    original = KNOWN_DETERMINISTIC_FAILURES.get("g004")
    KNOWN_DETERMINISTIC_FAILURES["g004"] = declared
    try:
        report = _report([_outcome("g004", runs=10, passes=0), _outcome("g005", passes=0)])
        assert report.gates["deterministic"] is False
        assert "g004" in report.out_of_band
    finally:
        KNOWN_DETERMINISTIC_FAILURES["g004"] = original


def test_an_undeclared_case_failing_even_once_is_unexpected():
    """This is what catches a case turning flaky, since undeclared cases run once."""
    report = _report(
        [
            _outcome("g004", runs=10, passes=2),
            _outcome("g005", passes=0),
            _outcome("g014", passes=0),
        ]
    )
    assert report.unexpected_failures == {"g014"}
    assert report.gates["deterministic"] is False


def test_the_headline_rate_averages_per_case_rather_than_counting_cases():
    """So the number stops moving between identical runs, which was the visible symptom.

    24 stable passes, g005 at 0, g004 at 0.2, over 26 cases.
    """
    outcomes = [_outcome(f"g{i:03d}") for i in range(100, 124)]
    outcomes += [_outcome("g004", runs=10, passes=2), _outcome("g005", passes=0)]
    report = _report(outcomes)
    assert report.deterministic_pass_rate == pytest.approx((24 + 0.2) / 26)


def test_only_declared_flaky_cases_repeat():
    """Repeats cost a full pipeline call each, so they stay bounded to what needs them."""
    assert _runs_for("g004", override=None) == 10
    assert _runs_for("g005", override=None) == 1
    assert _runs_for("g014", override=None) == 1


def test_the_runs_override_only_affects_cases_that_already_repeat():
    """--flaky-runs is for re-measuring a band, not for turning every case into 10."""
    assert _runs_for("g004", override=3) == 3
    assert _runs_for("g014", override=3) == 1


def test_a_stable_known_failure_is_a_zero_width_band():
    """g005 is declared with runs=1, so it behaves exactly as it did before."""
    declared = KNOWN_DETERMINISTIC_FAILURES["g005"]
    assert declared.runs == 1
    assert declared.holds(0.0) and not declared.holds(1.0)
    assert declared.band == "0%"


class _FakePlan:
    """The subset of a plan that `check_case` reads."""

    def __init__(self):
        self.citations = []
        self.retrieval = None
        self.refused = False


class _FakeAnswer:
    def __init__(self, text):
        self.text = text
        self.plan = _FakePlan()


@pytest.mark.asyncio
async def test_run_case_repeats_and_counts_each_attempt(monkeypatch):
    """The repeat loop itself, which the gate tests above take as given.

    A case whose answer alternates must be recorded as passing half its runs, not as
    whatever its first attempt happened to be.
    """
    import asyncio

    from winchat_api.evals import run as run_module

    texts = ["the deadline is April 1", "the deadline is March 1"]
    calls = {"n": 0}

    async def fake_answer_question(**_kwargs):
        text = texts[calls["n"] % len(texts)]
        calls["n"] += 1
        return _FakeAnswer(text)

    monkeypatch.setattr(run_module, "answer_question", fake_answer_question)

    case = GoldenCase(
        id="g004",
        question="when is the deadline?",
        category="answerable",
        must_include=["April 1"],
    )
    outcome = await run_module._run_case(
        case,
        pool=None,
        llm=None,
        judge=None,
        embedder=None,
        reranker=None,
        semaphore=asyncio.Semaphore(1),
        runs=10,
    )

    assert calls["n"] == 10, "every attempt must actually call the pipeline"
    assert outcome.runs == 10
    assert outcome.passes == 5
    assert outcome.pass_rate == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_run_case_judges_once_however_many_times_it_runs(monkeypatch):
    """The judge is the expensive tier; the variance being measured is not in it."""
    import asyncio

    from winchat_api.evals import run as run_module

    judged = {"n": 0}

    async def fake_answer_question(**_kwargs):
        return _FakeAnswer("an answer")

    async def fake_judge_answer(*_args, **_kwargs):
        judged["n"] += 1
        return None

    monkeypatch.setattr(run_module, "answer_question", fake_answer_question)
    monkeypatch.setattr(run_module, "judge_answer", fake_judge_answer)
    monkeypatch.setattr(run_module, "build_context", lambda _chunks: type("C", (), {"text": ""})())

    case = GoldenCase(id="g004", question="q", category="answerable")
    await run_module._run_case(
        case,
        pool=None,
        llm=None,
        judge=object(),
        embedder=None,
        reranker=None,
        semaphore=asyncio.Semaphore(1),
        runs=10,
    )
    assert judged["n"] == 1
