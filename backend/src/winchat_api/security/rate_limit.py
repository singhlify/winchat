"""Per-subject rate limiting and a global circuit breaker.

This is OWASP LLM10 (Unbounded Consumption), and it is a product feature as much as a
safeguard: an LLM endpoint without a spend ceiling is one scripted loop away from a
surprise invoice.

Two independent limits, because they stop different things:

* **Per-subject rolling window** — stops one user, signed in or not, from monopolising the
  service. A rolling window rather than a calendar hour: a fixed bucket lets someone spend
  the whole allowance at 10:59 and the whole next one at 11:00.
* **Global daily circuit breaker** — the actual spend ceiling. Per-user limits alone do not
  bound total cost, because the number of users is not bounded.

Postgres, not Redis. At this scale a counter table is two indexed queries, and adding a
second datastore before it is needed is the kind of complexity that reads as
over-engineering rather than sophistication. If the write volume ever justifies Redis, the
interface here does not change.

Anonymous callers are identified by a *salted hash* of their address. Rate limiting needs
to tell clients apart, which does not require storing anything that identifies a person.
"""

import hashlib
import logging
from dataclasses import dataclass

import asyncpg

from winchat_api.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Subject:
    key: str
    kind: str  # user | anonymous


@dataclass(frozen=True, slots=True)
class LimitDecision:
    allowed: bool
    reason: str = ""
    retry_after_s: int = 0
    used: int = 0
    limit: int = 0
    scope: str = ""


def anonymous_subject(client_ip: str) -> Subject:
    settings = get_settings()
    digest = hashlib.sha256(f"{settings.rate_limit_salt}:{client_ip}".encode()).hexdigest()
    return Subject(key=f"anon:{digest[:32]}", kind="anonymous")


def user_subject(user_id: str) -> Subject:
    return Subject(key=f"user:{user_id}", kind="user")


async def check_limits(
    pool: asyncpg.Pool, subject: Subject, *, bypass_subject_limits: bool = False
) -> LimitDecision:
    """Both limits, evaluated before any expensive work happens.

    `bypass_subject_limits` waives the PER-SUBJECT hourly and daily caps for a maintenance
    caller. It deliberately does NOT waive the global daily breaker below, and that
    asymmetry is the whole design:

    * the per-subject caps exist to stop one visitor monopolising a shared free tier —
      annoying during testing, and nothing worse than annoying to waive;
    * the global cap is the SPEND CEILING on the Groq and Cohere keys. A token that waived
      it would turn one leaked header into an unmetered bill, which is precisely the failure
      the limiter exists to prevent.

    So the maintenance path can test freely and still cannot cost more than the service was
    ever willing to spend in a day.
    """
    settings = get_settings()

    per_hour = settings.rate_limit_per_hour
    per_day = settings.rate_limit_per_day
    global_per_day = settings.rate_limit_global_per_day

    row = await pool.fetchrow(
        """
        select
            count(*) filter (where subject = $1 and occurred_at > now() - interval '1 hour')
                as subject_hour,
            count(*) filter (where subject = $1 and occurred_at > now() - interval '1 day')
                as subject_day,
            count(*) filter (where occurred_at > now() - interval '1 day')
                as global_day
        from usage_events
        where occurred_at > now() - interval '1 day'
        """,
        subject.key,
    )

    if row["global_day"] >= global_per_day:
        # Deliberately does not say "come back tomorrow" to the user — the breaker is an
        # operator concern, and the number is not something a caller should be probing.
        logger.warning("global daily circuit breaker tripped at %d requests", row["global_day"])
        return LimitDecision(
            allowed=False,
            reason="The service has reached its daily capacity. Please try again later.",
            retry_after_s=3600,
            used=row["global_day"],
            limit=global_per_day,
            scope="global_day",
        )

    if bypass_subject_limits:
        # Logged every time, at WARNING. A bypass nobody can see in the logs is a backdoor;
        # one that announces itself is an operational tool.
        logger.warning("maintenance bypass used for subject %s", subject.kind)
        return LimitDecision(
            allowed=True, used=row["subject_hour"], limit=per_hour, scope="maintenance_bypass"
        )

    if row["subject_hour"] >= per_hour:
        return LimitDecision(
            allowed=False,
            reason=f"Rate limit reached ({per_hour} questions per hour).",
            retry_after_s=600,
            used=row["subject_hour"],
            limit=per_hour,
            scope="subject_hour",
        )

    if row["subject_day"] >= per_day:
        return LimitDecision(
            allowed=False,
            reason=f"Daily limit reached ({per_day} questions per day).",
            retry_after_s=3600,
            used=row["subject_day"],
            limit=per_day,
            scope="subject_day",
        )

    return LimitDecision(
        allowed=True, used=row["subject_hour"], limit=per_hour, scope="subject_hour"
    )


async def record_usage(pool: asyncpg.Pool, subject: Subject, *, tokens: int = 0) -> None:
    """Record one billable request. Recorded on accept, so a refusal still counts.

    A refused question costs a retrieval and an embedding call, and counting only answered
    questions would leave an obvious hole: ask nonsense forever, free of charge.
    """
    await pool.execute(
        "insert into usage_events (subject, subject_kind, tokens) values ($1, $2, $3)",
        subject.key,
        subject.kind,
        tokens,
    )


async def purge_old_usage(pool: asyncpg.Pool, *, keep_days: int = 7) -> int:
    """Housekeeping — nothing older than the widest window is ever read."""
    result = await pool.execute(
        f"delete from usage_events where occurred_at < now() - interval '{int(keep_days)} days'"
    )
    return int(result.split()[-1]) if result.startswith("DELETE") else 0
