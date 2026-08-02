"""Rate-limit retry.

Providers meter by tokens per minute. When the budget is exhausted the correct response is
to wait exactly as long as the server says and try again — not to fail, and not to guess a
backoff. Groq returns both a `retry-after` header and a delay in the message body; we
prefer the server's number over any schedule of our own.

This lives outside the SDK's own retry because that one caps its total wait at a few
seconds. Draining a 60k-token workload through a 12k-per-minute budget needs waits
measured in minutes, so the schedule has to be ours.

Only rate limits are retried here. A 401 is not going to fix itself, and retrying a bad
request just multiplies it.
"""

import asyncio
import logging
import random
import re
import time
from collections.abc import Awaitable, Callable

from groq import RateLimitError

logger = logging.getLogger(__name__)

_DELAY_IN_MESSAGE = re.compile(r"try again in ([0-9.]+)\s*s", re.IGNORECASE)
MAX_DELAY_S = 65.0  # a token-per-minute window never needs longer than one minute


def suggested_delay(error: RateLimitError) -> float | None:
    """The wait the server asked for, from the header first and the message second."""
    response = getattr(error, "response", None)
    header = getattr(response, "headers", {}) or {}
    raw = header.get("retry-after")
    if raw:
        try:
            return min(float(raw), MAX_DELAY_S)
        except ValueError:
            pass

    match = _DELAY_IN_MESSAGE.search(str(error))
    if match:
        return min(float(match.group(1)), MAX_DELAY_S)
    return None


async def with_rate_limit_retry[T](
    call: Callable[[], Awaitable[T]], *, budget_s: float = 20.0, label: str = "call"
) -> T:
    """Retry rate limits until `budget_s` is spent.

    A time budget, not an attempt count: how long a caller is willing to wait is the real
    constraint, and it differs by caller. A user watching a chat box should wait seconds;
    an offline eval draining a whole suite through a per-minute budget can afford minutes.
    An attempt count cannot express either, because the wait per attempt is set by the
    server, not by us.
    """
    deadline = time.monotonic() + budget_s
    attempt = 0

    while True:
        attempt += 1
        try:
            return await call()
        except RateLimitError as exc:
            # Jitter matters: without it every concurrent worker wakes at the same instant
            # and re-exhausts the budget together.
            delay = (suggested_delay(exc) or min(2.0**attempt, 30.0)) + random.uniform(0.25, 1.5)
            if time.monotonic() + delay > deadline:
                logger.warning("%s rate-limited and out of retry budget (%.0fs)", label, budget_s)
                raise
            logger.info("%s rate-limited (attempt %d), waiting %.1fs", label, attempt, delay)
            await asyncio.sleep(delay)
