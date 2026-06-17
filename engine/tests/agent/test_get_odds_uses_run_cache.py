from __future__ import annotations

import asyncio

from tests.graph.conftest import build_graph_deps
from wolves.agent.tools.retrieval.get_odds import GetOddsArgs, _get_odds


async def test_get_odds_reuses_the_run_cache_for_parallel_calls(tmp_path):
    deps = build_graph_deps(tmp_path)
    args = GetOddsArgs(market="outrights")

    with deps.runtime.run_trace():
        first, second = await asyncio.gather(_get_odds(args, deps), _get_odds(args, deps))

    assert first.ok and second.ok
    assert first.payload == second.payload
    assert deps.odds.calls == ["outrights"]
    assert deps.polymarket.calls == 1
    assert deps.runtime.budget.data_fetches == 1
    deps.runtime.shutdown()
