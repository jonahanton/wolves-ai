from __future__ import annotations

import asyncio

from wolves.toolkit._budget_gate import BudgetGate


def test_reservations_stop_exactly_at_budget():
    gate = BudgetGate(budget=3)
    assert [gate.try_reserve() for _ in range(5)] == [True, True, True, False, False]
    assert gate.used == 3
    assert gate.exhausted


def test_zero_budget_means_unlimited():
    gate = BudgetGate(budget=0)
    assert all(gate.try_reserve() for _ in range(100))
    assert not gate.exhausted
    assert gate.remaining == 1


def test_remaining_counts_down():
    gate = BudgetGate(budget=2)
    assert gate.remaining == 2
    gate.try_reserve()
    assert gate.remaining == 1


def test_keep_free_reserves_a_floor_for_other_callers():
    gate = BudgetGate(budget=12)
    searches = sum(gate.try_reserve(keep_free=3) for _ in range(20))
    assert searches == 9
    assert gate.remaining == 3
    assert gate.try_reserve()


async def test_parallel_sibling_tasks_cannot_over_reserve():
    """All siblings dispatched in one turn race the gate; exactly `budget` win."""
    gate = BudgetGate(budget=4)

    async def attempt() -> bool:
        return gate.try_reserve()

    results = await asyncio.gather(*(attempt() for _ in range(20)))
    assert sum(results) == 4
    assert gate.used == 4
