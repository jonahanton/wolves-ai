"""Atomic tool-budget reservation primitive.

The model can emit several tool calls in a single assistant turn. Agent frameworks dispatch
sibling calls via ``asyncio.create_task`` on a single-threaded event loop.
Each budgeted tool must therefore perform a single check-and-increment
that cannot be interleaved by another sibling. A plain ``tools_used += 1``
was fine under strictly sequential dispatch, but under parallel dispatch all
siblings can pass a pre-hook "budget > 0" check before any of them increment.

``BudgetGate.try_reserve`` closes that gap: the sync body has no ``await`` so
it runs atomically under asyncio. If a future maintainer adds an ``await``
anywhere inside this class, the atomicity assumption breaks and an
``asyncio.Lock`` must be introduced at that point.
"""

from __future__ import annotations


class BudgetGate:
    """Atomic budget reservation for tool calls.

    Kept sync on purpose: in a single-threaded asyncio context, sync reads
    and writes cannot interleave, so no lock is needed. If this class ever
    gains an ``await`` internally, add an ``asyncio.Lock`` at that point.

    A budget of ``0`` or less means unlimited (gate never exhausts).
    """

    __slots__ = ("_budget", "_used")

    def __init__(self, budget: int = 0) -> None:
        self._budget = budget
        self._used = 0

    @property
    def limit(self) -> int:
        """Configured budget ceiling. 0 means unlimited."""
        return self._budget

    @property
    def used(self) -> int:
        return self._used

    @property
    def remaining(self) -> int:
        """Remaining reservations. Always >= 1 when the budget is unlimited."""
        if self._budget <= 0:
            return 1
        return max(0, self._budget - self._used)

    @property
    def exhausted(self) -> bool:
        return self._budget > 0 and self._used >= self._budget

    def try_reserve(self, *, keep_free: int = 0) -> bool:
        """Atomic check-and-increment. Returns ``False`` when exhausted.

        ``keep_free`` reserves a floor for other callers: a reservation only
        succeeds if at least ``keep_free`` slots would remain afterwards. A
        search passes the fetch floor so it cannot consume the slots a later
        fetch needs to back the evidence it cites; a fetch passes 0."""
        if self._budget > 0 and self._used + keep_free >= self._budget:
            return False
        self._used += 1
        return True


BUDGET_EXHAUSTED_MESSAGE = (
    "Budget exhausted. No more tool calls available. Synthesise an answer from the material already gathered."
)


def budget_exhausted_message() -> str:
    """Standard message returned by tools that could not reserve a slot."""
    return BUDGET_EXHAUSTED_MESSAGE
