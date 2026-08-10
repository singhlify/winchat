"""Rate-limit retry. Waits the interval the provider reports rather than guessing a backoff."""

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
    """Retry rate limits until `budget_s` is spent. A time budget rather than an attempt count,
    because callers differ: a user waits seconds, an offline suite can wait minutes.
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
