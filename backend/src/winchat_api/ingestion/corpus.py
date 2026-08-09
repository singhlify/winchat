"""Reading the scraped corpus off disk.

The scraper's output is the contract: one JSON object per line, keyed by `a_id`. This module
is the only place that knows that format, so re-scraping or changing the source shape touches
one file.
"""

import hashlib
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

REQUIRED_FIELDS = ("a_id", "question", "answer_text", "url")

# Every citation the app renders is a link the user is invited to trust, shown next to a
# University of Windsor answer. The URL comes from a file on disk, so nothing downstream
# distinguishes "scraped from ask.uwindsor.ca" from "someone edited answers.jsonl" — the UI
# lends its credibility to whatever host ends up in this field.
ALLOWED_SOURCE_HOSTS = frozenset({"ask.uwindsor.ca"})


@dataclass(frozen=True, slots=True)
class Answer:
    a_id: str
    question: str
    answer_text: str
    url: str
    lastmod: datetime | None
    fetched_at: datetime | None

    @property
    def content_hash(self) -> str:
        """Identifies the *content*, so a changed lastmod alone does not force re-embedding."""
        payload = f"{self.question}\n{self.answer_text}".encode()
        return hashlib.sha256(payload).hexdigest()


class CorpusError(RuntimeError):
    """The corpus file is missing or a record is unusable."""


def normalize_whitespace(text: str) -> str:
    """Tidy scraped text: trailing spaces and runs of blank lines add tokens, not meaning."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def load_answers(path: Path) -> list[Answer]:
    """Read every answer, skipping nothing silently — a bad record raises."""
    if not path.exists():
        raise CorpusError(f"corpus not found at {path}; run scripts/scrape_ask_uwindsor.py first")

    answers = list(_iter_answers(path))
    if not answers:
        raise CorpusError(f"corpus at {path} is empty")

    duplicates = len(answers) - len({answer.a_id for answer in answers})
    if duplicates:
        raise CorpusError(f"corpus contains {duplicates} duplicate a_id values")

    return answers


def _check_source(url: str, path: Path, line_number: int) -> None:
    """Refuse an answer whose URL is not from an allowed source.

    Fails the whole ingest rather than skipping the row. A corpus with unexpected hosts in it is
    not a corpus with one bad line — it is a file that is not what it claims to be, and quietly
    dropping rows would hide that.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise CorpusError(f"{path}:{line_number} url is not http(s): {parsed.scheme or 'none'}://…")

    # Compare the host exactly. A suffix check (`endswith('uwindsor.ca')`) would accept
    # `uwindsor.ca.attacker.example`, which is the classic way this check gets written wrong.
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_SOURCE_HOSTS:
        raise CorpusError(
            f"{path}:{line_number} url host {host!r} is not an allowed source "
            f"({', '.join(sorted(ALLOWED_SOURCE_HOSTS))}). "
            "If the corpus legitimately gained a new source, add it to ALLOWED_SOURCE_HOSTS "
            "deliberately — do not widen this to make an ingest pass."
        )


def _iter_answers(path: Path) -> Iterator[Answer]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CorpusError(f"{path}:{line_number} is not valid JSON ({exc})") from exc

            missing = [field for field in REQUIRED_FIELDS if not record.get(field)]
            if missing:
                raise CorpusError(f"{path}:{line_number} is missing {', '.join(missing)}")

            _check_source(record["url"], path, line_number)

            yield Answer(
                a_id=str(record["a_id"]),
                question=normalize_whitespace(record["question"]),
                answer_text=normalize_whitespace(record["answer_text"]),
                url=record["url"],
                lastmod=_parse_timestamp(record.get("lastmod")),
                fetched_at=_parse_timestamp(record.get("fetched_at")),
            )
