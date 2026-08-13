"""The eval harness. Exits non-zero when a gate fails.

uv run python -m winchat_api.evals.run [--tier1] [--json out.json]
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import asyncpg

from winchat_api.chat.context import build_context
from winchat_api.chat.service import answer_question
from winchat_api.config import get_settings
from winchat_api.db.pool import create_pool
from winchat_api.embeddings.registry import get_embedding_provider
from winchat_api.evals.dataset import GoldenCase, load_golden_set
from winchat_api.evals.judge import Verdict, judge_answer
from winchat_api.evals.metrics import (
    DeterministicResult,
    check_case,
    mean_reciprocal_rank,
    recall,
    refusal_accuracy,
)
from winchat_api.llm.base import ChatProvider
from winchat_api.llm.registry import build_chat_provider
from winchat_api.retrieval.rerank.registry import get_reranker

logger = logging.getLogger("evals")


@dataclass
class CaseOutcome:
    case: GoldenCase
    answer: str
    refused: bool
    deterministic: DeterministicResult
    verdict: Verdict | None = None
    latency_ms: float = 0.0
    runs: int = 1
    passes: int = 0

    @property
    def pass_rate(self) -> float:
        return self.passes / self.runs


@dataclass(frozen=True)
class KnownFailure:
    """A defect that is documented rather than fixed, tracked in KNOWN_ISSUES.md.

    Some of these fail only some of the time. Temperature 0.0 makes decoding greedy, it
    does not make a hosted provider reproducible: batched inference and non-associative
    floating point can flip a near-tied token, and the rest of the generation diverges
    from there. Scoring such a case on a single run measures the sample rather than the
    defect, which is how g004 came to be reported as fixed by a run where it got lucky.

    So a flaky case declares the pass-rate band it is expected to stay inside and is run
    `runs` times. Drifting out of that band in either direction breaks the build, which
    is the same invariant the exact-match set had: the documentation cannot go stale
    without someone noticing. Bands are measured, never guessed.
    """

    reason: str
    runs: int = 1
    min_rate: float = 0.0
    max_rate: float = 0.0

    def holds(self, rate: float) -> bool:
        return self.min_rate - 1e-9 <= rate <= self.max_rate + 1e-9

    @property
    def band(self) -> str:
        if self.min_rate == self.max_rate:
            return f"{self.min_rate:.0%}"
        return f"{self.min_rate:.0%} to {self.max_rate:.0%}"


# The gate requires reality to match these declarations exactly, so a new failure, a fixed
# one, and a flaky one drifting out of its band all break the build.
KNOWN_DETERMINISTIC_FAILURES = {
    "g004": KnownFailure(
        "corpus conflict, a_id 594 and 604 give different graduate deadlines",
        # Measured at 2/10 on 2026-08-12. The band is wide because 10 runs pins a rate
        # only loosely: the 95% Wilson interval on 2/10 runs from 6% to 51%.
        runs=10,
        min_rate=0.0,
        max_rate=0.6,
    ),
    "g005": KnownFailure("procedural answer drops the named UI element"),
}


@dataclass
class Report:
    model: str
    judge_model: str
    reranker: str
    cases: int
    deterministic_pass_rate: float
    retrieval_recall: float
    retrieval_mrr: float
    refusal_accuracy: float
    faithfulness: float | None
    correctness: float | None
    judged: int
    duration_s: float
    deterministic_failed_ids: set[str] = field(default_factory=set)
    unexpected_failures: set[str] = field(default_factory=set)
    # Declared known failures whose measured pass rate left its band, in either direction.
    out_of_band: dict[str, str] = field(default_factory=dict)
    observed_rates: dict[str, float] = field(default_factory=dict)
    failures: list[dict] = field(default_factory=list)
    gates: dict[str, bool] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(self.gates.values())


async def _run_case(
    case: GoldenCase,
    *,
    pool: asyncpg.Pool,
    llm: ChatProvider,
    judge: ChatProvider | None,
    embedder,
    reranker,
    semaphore: asyncio.Semaphore,
    runs: int = 1,
) -> CaseOutcome:
    """Run one case `runs` times and record how often it passed.

    Only declared-flaky cases repeat, so the cost is bounded to the handful that need it.
    An undeclared case that fails on any run is still an unexpected failure, which is the
    behaviour that catches a case turning flaky in the first place.

    The judge runs once, on the first attempt. It is the expensive tier and the variance
    being measured here is in the deterministic checks, not in the judging.
    """
    outcome: CaseOutcome | None = None
    passes = 0

    for attempt in range(runs):
        async with semaphore:
            started = time.perf_counter()
            answer = await answer_question(
                pool=pool, llm=llm, embedder=embedder, reranker=reranker, question=case.question
            )
            latency_ms = round((time.perf_counter() - started) * 1000, 1)

            plan = answer.plan
            deterministic = check_case(
                case,
                answer=answer.text,
                citations=plan.citations,
                retrieval=plan.retrieval,
                refused=plan.refused,
            )

            verdict = None
            if judge is not None and attempt == 0:
                context = build_context(plan.retrieval.chunks if plan.retrieval else []).text
                verdict = await judge_answer(
                    judge, question=case.question, answer=answer.text, context=context
                )

        passes += deterministic.passed
        if outcome is None:
            # Retrieval is the same on every attempt, so recall and MRR are read off the
            # first one. It is only the checks that read the generated text that move.
            outcome = CaseOutcome(
                case=case,
                answer=answer.text,
                refused=plan.refused,
                deterministic=deterministic,
                verdict=verdict,
                latency_ms=latency_ms,
                runs=runs,
            )

    assert outcome is not None  # runs is >= 1
    outcome.passes = passes
    return outcome


def _rate(values: list[bool]) -> float | None:
    return sum(values) / len(values) if values else None


def _runs_for(case_id: str, *, override: int | None) -> int:
    """How many times to run a case. Only declared-flaky cases repeat."""
    declared = KNOWN_DETERMINISTIC_FAILURES.get(case_id)
    if declared is None or declared.runs == 1:
        return 1
    return max(1, override or declared.runs)


def build_report(outcomes: list[CaseOutcome], *, model, judge_model, reranker, duration) -> Report:
    settings = get_settings()
    cases = [outcome.case for outcome in outcomes]
    deterministic = [outcome.deterministic for outcome in outcomes]

    judged = [o.verdict for o in outcomes if o.verdict is not None]
    faithful = [v.faithful for v in judged if v.faithful is not None]
    correct = [v.correct for v in judged if v.correct is not None]

    report = Report(
        model=model,
        judge_model=judge_model,
        reranker=reranker,
        cases=len(outcomes),
        # Mean of the per-case pass rates, not the share of cases that passed. A case run
        # once contributes 0 or 1 exactly as before; a flaky one contributes its measured
        # rate, which is what stops this headline number moving between identical runs.
        deterministic_pass_rate=sum(o.pass_rate for o in outcomes) / len(outcomes),
        retrieval_recall=recall(deterministic),
        retrieval_mrr=mean_reciprocal_rank(deterministic),
        refusal_accuracy=refusal_accuracy(deterministic, cases),
        faithfulness=_rate(faithful),
        correctness=_rate(correct),
        judged=len(faithful),
        duration_s=round(duration, 1),
    )

    # A case counts as failed if it failed on any attempt. For a case that runs once this
    # is the old behaviour exactly; for a flaky one it is what makes a single lucky run
    # unable to report the defect as fixed.
    report.deterministic_failed_ids = {
        outcome.case.id for outcome in outcomes if outcome.passes < outcome.runs
    }
    known = set(KNOWN_DETERMINISTIC_FAILURES)
    report.unexpected_failures = report.deterministic_failed_ids - known

    for outcome in outcomes:
        declared = KNOWN_DETERMINISTIC_FAILURES.get(outcome.case.id)
        if declared is None:
            continue
        report.observed_rates[outcome.case.id] = outcome.pass_rate
        if not declared.holds(outcome.pass_rate):
            report.out_of_band[outcome.case.id] = (
                f"passed {outcome.passes} of {outcome.runs}, "
                f"which is {outcome.pass_rate:.0%}, outside the declared {declared.band}"
            )

    for outcome in outcomes:
        problems = list(outcome.deterministic.failures)
        # A flaky case may well pass its first attempt, so it would otherwise be invisible
        # here despite having failed later ones.
        if outcome.runs > 1 and outcome.passes < outcome.runs:
            note = "; any checks above are from the first" if outcome.deterministic.failures else ""
            problems.append(
                f"passed {outcome.passes} of {outcome.runs} runs ({outcome.pass_rate:.0%}){note}"
            )
        if outcome.verdict and outcome.verdict.faithful is False:
            problems.append(f"judged unfaithful: {outcome.verdict.faithfulness_reason}")
        if outcome.verdict and outcome.verdict.correct is False:
            problems.append(f"judged incorrect: {outcome.verdict.correctness_reason}")
        if problems:
            report.failures.append(
                {
                    "id": outcome.case.id,
                    "question": outcome.case.question,
                    "problems": problems,
                    "answer": outcome.answer[:400],
                }
            )

    # No percentage slack, so the known-failure list cannot go stale. Flaky cases get a
    # band rather than a boolean, but the band is still an assertion that has to hold.
    report.gates = {
        "deterministic": not report.unexpected_failures and not report.out_of_band,
        "retrieval_recall": report.retrieval_recall >= settings.eval_min_retrieval_recall,
    }
    if report.faithfulness is not None:
        report.gates["faithfulness"] = report.faithfulness >= settings.eval_min_faithfulness
    if report.correctness is not None:
        report.gates["correctness"] = report.correctness >= settings.eval_min_correctness

    return report


def print_report(report: Report) -> None:
    def pct(value: float | None) -> str:
        return "  n/a" if value is None else f"{value:6.1%}"

    print("\n" + "=" * 68)
    print(f"  model  {report.model}")
    print(f"  judge  {report.judge_model}")
    print(f"  rerank {report.reranker}   cases {report.cases}   {report.duration_s}s")
    print("-" * 68)
    print(f"  deterministic pass   {pct(report.deterministic_pass_rate)}")
    print(f"  retrieval recall     {pct(report.retrieval_recall)}")
    print(f"  retrieval MRR        {report.retrieval_mrr:6.3f}")
    print(f"  refusal accuracy     {pct(report.refusal_accuracy)}")
    print(f"  faithfulness         {pct(report.faithfulness)}  ({report.judged} judged)")
    print(f"  correctness          {pct(report.correctness)}")
    print("-" * 68)

    if report.failures:
        print(f"  {len(report.failures)} case(s) with problems:\n")
        for failure in report.failures:
            print(f"  {failure['id']}  {failure['question']}")
            for problem in failure["problems"]:
                print(f"      - {problem}")
            print()

    if report.observed_rates:
        print("  known failures, measured:")
        for case_id, rate in sorted(report.observed_rates.items()):
            declared = KNOWN_DETERMINISTIC_FAILURES[case_id]
            runs = f" over {declared.runs} runs" if declared.runs > 1 else ""
            print(f"      {case_id}  passed {rate:.0%}{runs}, declared {declared.band}")
        print()

    if report.unexpected_failures:
        print(f"\n  UNEXPECTED failures: {', '.join(sorted(report.unexpected_failures))}")
    if report.out_of_band:
        print("\n  known failures outside their declared band:")
        for case_id, detail in sorted(report.out_of_band.items()):
            print(f"      {case_id}  {detail}")
        print(
            "  Re-measure before editing a band, and never close an issue on one lucky run.\n"
            "  A rate that has genuinely reached 100% means fixed: remove it and close it."
        )
    for name, passed in report.gates.items():
        print(f"  gate {name:<18} {'PASS' if passed else 'FAIL'}")
    print("=" * 68)
    print(f"  {'PASSED' if report.passed else 'FAILED'}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the evaluation suite.")
    parser.add_argument("--golden", type=Path, default=None)
    parser.add_argument("--tier1", action="store_true", help="deterministic checks only")
    parser.add_argument("--json", type=Path, default=None, help="write the full report here")
    parser.add_argument("--model", type=str, default=None, help="override the model under test")
    parser.add_argument("--concurrency", type=int, default=None, help="parallel cases")
    parser.add_argument(
        "--flaky-runs",
        type=int,
        default=None,
        help="override how many times declared-flaky cases run, for re-measuring a band",
    )
    parser.add_argument("--no-gate", action="store_true", help="always exit 0")
    return parser.parse_args()


async def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    args = parse_args()
    settings = get_settings()

    cases = load_golden_set(args.golden)
    model = args.model or settings.eval_model
    budget = settings.eval_retry_budget_s
    llm = build_chat_provider(model=model, retry_budget_s=budget)
    judge = (
        None
        if args.tier1
        else build_chat_provider(model=settings.eval_judge_model, retry_budget_s=budget)
    )
    reranker = get_reranker()
    embedder = get_embedding_provider()

    print(
        f"running {len(cases)} cases against {model}"
        + ("" if judge is None else f", judged by {settings.eval_judge_model}")
    )

    concurrency = args.concurrency or settings.eval_concurrency
    pool = await create_pool(max_size=concurrency + 2)
    semaphore = asyncio.Semaphore(concurrency)
    started = time.perf_counter()
    try:
        outcomes = await asyncio.gather(
            *[
                _run_case(
                    case,
                    pool=pool,
                    llm=llm,
                    judge=judge,
                    embedder=embedder,
                    reranker=reranker,
                    semaphore=semaphore,
                    runs=_runs_for(case.id, override=args.flaky_runs),
                )
                for case in cases
            ]
        )
    finally:
        await pool.close()

    report = build_report(
        outcomes,
        model=model,
        judge_model="none" if judge is None else settings.eval_judge_model,
        reranker=reranker.name,
        duration=time.perf_counter() - started,
    )
    print_report(report)

    if args.json:
        payload = asdict(report)
        payload["cases"] = [
            {
                "id": o.case.id,
                "category": o.case.category,
                "question": o.case.question,
                "answer": o.answer,
                "refused": o.refused,
                "passed": o.passes == o.runs,
                "deterministic": o.deterministic.passed,
                "runs": o.runs,
                "passes": o.passes,
                "pass_rate": o.pass_rate,
                "failures": o.deterministic.failures,
                "retrieval_hit": o.deterministic.retrieval_hit,
                "retrieval_rank": o.deterministic.retrieval_rank,
                # Scored only where a refusal is expected, matching metrics.refusal_accuracy.
                # A second definition of the same metric would drift from it.
                "refusal_correct": (
                    None
                    if not o.case.expect_refusal
                    else not any("refus" in f for f in o.deterministic.failures)
                ),
                "faithful": None if o.verdict is None else o.verdict.faithful,
                "correct": None if o.verdict is None else o.verdict.correct,
                "verdict": asdict(o.verdict) if o.verdict else None,
                "latency_ms": o.latency_ms,
            }
            for o in outcomes
        ]
        payload["generated_at"] = datetime.now(UTC).strftime("%Y-%m-%d")
        payload["known_failures"] = {
            case_id: asdict(declared) for case_id, declared in KNOWN_DETERMINISTIC_FAILURES.items()
        }
        for key in ("deterministic_failed_ids", "unexpected_failures"):
            payload[key] = sorted(payload.get(key) or [])
        args.json.write_text(json.dumps(payload, indent=2))
        print(f"wrote {args.json}")

    return 0 if (report.passed or args.no_gate) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
