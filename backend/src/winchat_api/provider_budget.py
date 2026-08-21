"""A hard ceiling on paid provider calls made by one process.

The request path is metered by `check_limits`, which keys on the caller. The scheduled jobs
have no caller and never pass through it, so nothing counted their spend: the retry budgets
bound how long one call may wait, never how many calls a run makes. Every retry is a billable
call, so attempts are counted rather than logical operations.

Unset in the API, where the rate limiter is the ceiling. Set by the batch entry points, where
exceeding it aborts the run: a job that quietly stopped embedding would leave a half-updated
index behind and report success.
"""

import logging

logger = logging.getLogger(__name__)


class ProviderBudgetExceeded(RuntimeError):
    """A run asked for more paid provider calls than it was allowed. Never caught internally."""


class CallBudget:
    """Counts provider attempts. `limit=None` counts without ever refusing."""

    def __init__(self, limit: int | None = None) -> None:
        self.limit = limit
        self.spent = 0

    def spend(self, label: str) -> None:
        self.spent += 1
        if self.limit is not None and self.spent > self.limit:
            raise ProviderBudgetExceeded(
                f"{label}: provider call {self.spent} exceeds this run's ceiling of "
                f"{self.limit}. Raise --max-provider-calls deliberately if the work grew."
            )


_budget = CallBudget()


def set_call_budget(limit: int | None) -> CallBudget:
    """Install a fresh budget for this process and return it, so a caller can report on it."""
    global _budget
    _budget = CallBudget(limit)
    return _budget


def current_budget() -> CallBudget:
    return _budget


def spend(label: str) -> None:
    _budget.spend(label)
