"""Turns an eval run into a markdown table with confidence intervals.

uv run python -m winchat_api.evals.report eval-report.json > table.md
"""

import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# 95% two-sided.
Z = 1.959963984540054

# Below this many cases the interval spans most of the range, so the point estimate carries
# almost no information on its own.
THIN_N = 8


@dataclass(frozen=True, slots=True)
class Proportion:
    label: str
    numerator: int
    denominator: int

    @property
    def point(self) -> float | None:
        if self.denominator == 0:
            return None
        return self.numerator / self.denominator

    @property
    def interval(self) -> tuple[float, float] | None:
        return wilson(self.numerator, self.denominator)


def wilson(successes: int, total: int, z: float = Z) -> tuple[float, float] | None:
    """Wilson score interval for a binomial proportion.

    Used rather than the Wald interval because Wald collapses to zero width at p = 0 and
    p = 1, which is exactly where this suite sits.
    """
    if total <= 0:
        return None
    if successes < 0 or successes > total:
        raise ValueError(f"{successes} successes out of {total}")

    p = successes / total
    denominator = 1 + z**2 / total
    centre = p + z**2 / (2 * total)
    spread = z * math.sqrt(p * (1 - p) / total + z**2 / (4 * total**2))
    low = (centre - spread) / denominator
    high = (centre + spread) / denominator
    return max(0.0, low), min(1.0, high)


def _format(value: Proportion) -> str:
    if value.denominator == 0:
        return "| n/a | 0 | not measured |"
    low, high = value.interval
    note = " (n too small to be informative)" if value.denominator < THIN_N else ""
    return (
        f"| {value.point:.1%} | {value.numerator}/{value.denominator} "
        f"| {low:.1%} to {high:.1%}{note} |"
    )


def _table(title: str, rows: list[Proportion]) -> str:
    lines = [
        f"### {title}",
        "",
        "| metric | estimate | passed/total | 95% interval |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| {row.label} {_format(row)}")
    lines.append("")
    return "\n".join(lines)


def _counts(cases: list[dict], key: str) -> tuple[int, int]:
    scored = [c for c in cases if c.get(key) is not None]
    return sum(1 for c in scored if c[key]), len(scored)


def build_markdown(payload: dict) -> str:
    cases = payload["cases"]
    generated = payload.get("generated_at") or datetime.now(UTC).strftime("%Y-%m-%d")

    def group(subset: list[dict]) -> list[Proportion]:
        rows = [
            Proportion("deterministic checks", *_counts(subset, "deterministic")),
            Proportion("retrieval recall", *_counts(subset, "retrieval_hit")),
            Proportion("refusal accuracy", *_counts(subset, "refusal_correct")),
            Proportion("faithfulness", *_counts(subset, "faithful")),
            Proportion("correctness", *_counts(subset, "correct")),
        ]
        return [r for r in rows if r.denominator > 0]

    out = [
        f"Generated {generated} by `uv run python -m winchat_api.evals.report`.",
        "",
        f"Model `{payload['model']}`, judged by `{payload['judge_model']}`, "
        f"reranker `{payload['reranker']}`.",
        "",
        _table(f"Aggregate ({len(cases)} cases)", group(cases)),
    ]

    by_category: dict[str, list[dict]] = defaultdict(list)
    for case in cases:
        by_category[case.get("category", "uncategorised")].append(case)

    for category in sorted(by_category):
        subset = by_category[category]
        out.append(_table(f"{category} ({len(subset)} cases)", group(subset)))

    mrr = payload.get("retrieval_mrr")
    if mrr is not None:
        out.append(
            f"Mean reciprocal rank is {mrr:.3f}. It is a mean of per-case ranks rather than a "
            "proportion, so no binomial interval applies to it.\n"
        )

    known = payload.get("known_failures") or {}
    if known:
        out.append("### Known failures\n")
        out.append("| case | defect |")
        out.append("|---|---|")
        for case_id in sorted(known):
            out.append(f"| `{case_id}` | {known[case_id]} |")
        out.append("")

    return "\n".join(out)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m winchat_api.evals.report <eval-report.json>", file=sys.stderr)
        return 2
    payload = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    print(build_markdown(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
