"""The golden set: hand-written cases with verified expectations.

Every `must_include` value was read out of the actual corpus, not guessed. A golden set whose
expectations were invented measures nothing, it just encodes the author's assumptions and then
confirms them.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from winchat_api.config import BACKEND_ROOT

DEFAULT_GOLDEN_PATH = BACKEND_ROOT / "evals" / "golden" / "uwindsor.jsonl"


@dataclass(frozen=True, slots=True)
class GoldenCase:
    id: str
    question: str
    category: str  # answerable | refusal | adversarial
    note: str = ""
    expected_a_ids: list[str] = field(default_factory=list)
    must_include: list[str] = field(default_factory=list)
    must_not_include: list[str] = field(default_factory=list)
    must_not_match: str | None = None  # regex the answer must NOT match
    expect_refusal: bool = False
    expect_grounded_decline: bool = False

    @property
    def is_scored_for_retrieval(self) -> bool:
        return bool(self.expected_a_ids)


class GoldenSetError(RuntimeError):
    pass


def load_golden_set(path: Path | None = None) -> list[GoldenCase]:
    path = path or DEFAULT_GOLDEN_PATH
    if not path.exists():
        raise GoldenSetError(f"golden set not found at {path}")

    cases: list[GoldenCase] = []
    seen: set[str] = set()

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GoldenSetError(f"{path}:{line_number} is not valid JSON ({exc})") from exc

        case_id = record.get("id")
        if not case_id:
            raise GoldenSetError(f"{path}:{line_number} has no id")
        if case_id in seen:
            raise GoldenSetError(f"{path}:{line_number} duplicates case id {case_id}")
        seen.add(case_id)

        cases.append(GoldenCase(**record))

    if not cases:
        raise GoldenSetError(f"golden set at {path} is empty")
    return cases
