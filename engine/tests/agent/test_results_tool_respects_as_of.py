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


async def test_results_tool_resolves_matches_to_tournament_groups(tmp_path):
    deps = build_graph_deps(tmp_path)

    with deps.runtime.run_trace():
        result = await _get_results_and_fixtures(GetResultsAndFixturesArgs(date="2026-06-12"), deps)

    assert result.ok
    assert result.payload is not None
    [match] = result.payload["matches"]
    assert match["resolved"] is True
    assert match["match"] == 29
    assert match["group"] == "C"
    assert match["home_id"] == "brazil"
    assert match["away_id"] == "haiti"
    group_c = next(group for group in result.payload["group_tables"] if group["group"] == "C")
    assert group_c["teams"][0]["team_id"] == "brazil"
    assert group_c["teams"][0]["points"] == 3
    deps.runtime.shutdown()


async def test_results_tool_group_tables_use_all_known_results_through_as_of(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.as_of = "2026-06-14"

    with deps.runtime.run_trace():
        result = await _get_results_and_fixtures(GetResultsAndFixturesArgs(date="2026-06-12"), deps)

    assert result.ok
    assert result.payload is not None
    assert result.payload["group_tables_scope"] == "all known fixtures through 2026-06-14"
    group_a = next(group for group in result.payload["group_tables"] if group["group"] == "A")
    group_c = next(group for group in result.payload["group_tables"] if group["group"] == "C")
    group_g = next(group for group in result.payload["group_tables"] if group["group"] == "G")
    assert group_a["teams"][0]["team_id"] == "mexico"
    assert group_a["teams"][0]["points"] == 3
    assert group_c["teams"][0]["team_id"] == "brazil"
    assert group_c["teams"][0]["points"] == 3
    assert all(team["played"] == 0 for team in group_g["teams"])
    deps.runtime.shutdown()
