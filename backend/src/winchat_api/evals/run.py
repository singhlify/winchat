"""The eval harness. uv run python -m winchat_api.evals.run # both tiers, gated uv run python -m
winchat_api.evals.run --tier1 # deterministic only, no model cost uv run python -m
winchat_api.evals.run --json out.json Exits non-zero when any gate fails, which is what makes it
a CI gate rather than a report.

It runs the real pipeline. The same `answer_question` the HTTP endpoint calls. An eval that
exercises a parallel implementation eventually measures something the users never touch.
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
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
) -> CaseOutcome:
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
        if judge is not None:
            context = build_context(plan.retrieval.chunks if plan.retrieval else []).text
            verdict = await judge_answer(
                judge, question=case.question, answer=answer.text, context=context
            )

        return CaseOutcome(
            case=case,
            answer=answer.text,
            refused=plan.refused,
            deterministic=deterministic,
            verdict=verdict,
            latency_ms=latency_ms,
        )


def _rate(values: list[bool]) -> float | None:
    return sum(values) / len(values) if values else None


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
        deterministic_pass_rate=sum(1 for d in deterministic if d.passed) / len(deterministic),
        retrieval_recall=recall(deterministic),
        retrieval_mrr=mean_reciprocal_rank(deterministic),
        refusal_accuracy=refusal_accuracy(deterministic, cases),
        faithfulness=_rate(faithful),
        correctness=_rate(correct),
        judged=len(faithful),
        duration_s=round(duration, 1),
    )

    for outcome in outcomes:
        problems = list(outcome.deterministic.failures)
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

    report.gates = {
        "deterministic": report.deterministic_pass_rate >= settings.eval_min_deterministic_pass,
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
                "passed": o.deterministic.passed,
                "failures": o.deterministic.failures,
                "retrieval_rank": o.deterministic.retrieval_rank,
                "verdict": asdict(o.verdict) if o.verdict else None,
                "latency_ms": o.latency_ms,
            }
            for o in outcomes
        ]
        args.json.write_text(json.dumps(payload, indent=2))
        print(f"wrote {args.json}")

    return 0 if (report.passed or args.no_gate) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
