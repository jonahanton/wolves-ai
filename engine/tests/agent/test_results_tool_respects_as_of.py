from __future__ import annotations

from tests.graph.conftest import build_graph_deps
from wolves.agent.tools.retrieval.get_results_and_fixtures import GetResultsAndFixturesArgs, _get_results_and_fixtures


async def test_results_tool_refuses_dates_after_as_of(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.as_of = "2026-06-14"

    result = await _get_results_and_fixtures(GetResultsAndFixturesArgs(date="2026-06-15"), deps)

    assert not result.ok
    assert result.error is not None
    assert result.error.type == "invalid_arguments"
    assert "after today 2026-06-14" in result.error.message
    deps.runtime.shutdown()


async def test_results_tool_allows_the_as_of_date(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.as_of = "2026-06-14"

    with deps.runtime.run_trace():
        result = await _get_results_and_fixtures(GetResultsAndFixturesArgs(date="2026-06-14"), deps)

    assert result.ok
    assert result.payload is not None
    deps.runtime.shutdown()
