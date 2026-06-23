from __future__ import annotations

from pathlib import Path

import pytest

from tests.graph.conftest import build_graph_deps
from wolves.agent.scenarios import ScenarioRegistry, UnknownScenarioError
from wolves.agent.tools.memory.scenario_update import ScenarioUpdateArgs, _scenario_update


def test_lifecycle_survives_reload_and_tracks_unresolved(tmp_path: Path):
    path = tmp_path / "agent-state" / "scenarios.jsonl"
    registry = ScenarioRegistry(path)
    opened = registry.open(name="saka_misses_group", run_id="agent-d1", weight=0.33, reason="fitness doubt")
    assert opened.scenario_id == "scn-001"
    second = registry.open(name="dallas_heat", run_id="agent-d1", weight=0.3, reason="forecast 38C")
    assert second.scenario_id == "scn-002"

    reloaded = ScenarioRegistry(path)
    assert [s.scenario_id for s in reloaded.open_scenarios()] == ["scn-001", "scn-002"]
    assert [s.scenario_id for s in reloaded.unresolved_in("agent-d2")] == ["scn-001", "scn-002"]

    reloaded.update("scn-001", run_id="agent-d2", status="collapsed", weight=0.0, reason="declared fit")
    reloaded.update("scn-002", run_id="agent-d2", status="reweighted", weight=0.2, reason="cooler forecast")

    final = ScenarioRegistry(path)
    assert [s.scenario_id for s in final.open_scenarios()] == ["scn-002"]
    assert final.get("scn-002").weight == 0.2
    assert final.unresolved_in("agent-d2") == []
    assert final.get("scn-001").status == "collapsed"
    assert len(final.get("scn-001").history) == 2

    with pytest.raises(UnknownScenarioError):
        final.update("scn-999", run_id="agent-d2", status="collapsed", weight=0.0, reason="x")


def test_deferred_scenario_writes_commit_or_roll_back(tmp_path: Path):
    path = tmp_path / "agent-state" / "scenarios.jsonl"
    registry = ScenarioRegistry(path, defer_writes=True)

    opened = registry.open(name="saka_misses_group", run_id="agent-d1", weight=0.33, reason="fitness doubt")
    assert opened.scenario_id == "scn-001"
    assert not path.exists()

    registry.rollback()
    assert registry.open_scenarios() == []
    assert not path.exists()

    registry.open(name="saka_misses_group", run_id="agent-d2", weight=0.2, reason="new doubt")
    registry.commit()

    reloaded = ScenarioRegistry(path)
    assert [s.scenario_id for s in reloaded.open_scenarios()] == ["scn-001"]


async def test_update_resolves_one_exact_open_name(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    deps.scenarios = ScenarioRegistry(tmp_path / "agent-state" / "scenarios.jsonl")
    deps.scenarios.open(name="france_partial", run_id="agent-d1", weight=0.2, reason="market gap")

    with deps.runtime.run_trace():
        result = await _scenario_update(
            ScenarioUpdateArgs(action="collapse", name="france_partial", reason="below floor"),
            deps,
        )
    deps.runtime.shutdown()

    assert result.ok
    assert result.payload["status"] == "collapsed"
