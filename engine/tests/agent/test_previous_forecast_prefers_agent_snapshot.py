from __future__ import annotations

from pathlib import Path

import pytest

from tests.graph.conftest import build_graph_deps
from wolves.agent.tools.memory.previous_forecast import PreviousForecastArgs, _previous_forecast
from wolves.snapshot import (
    AgentBlock,
    FocusTeamBlock,
    NarrativeBlock,
    RunMeta,
    Snapshot,
    TeamInfo,
    WorldOut,
)


def _snapshot(*, run_id: str, created_at: str, kind: str, agent: AgentBlock | None = None) -> Snapshot:
    return Snapshot(
        run=RunMeta(
            run_id=run_id,
            created_at=created_at,
            as_of="2026-06-13",
            n_sims=100,
            engine_version="0",
            kind=kind,
        ),
        focus=FocusTeamBlock(team_id="england", group="L", finish_probs={}, reach_probs={"champion": 0.1}, paths=[]),
        slots=[],
        teams=[
            TeamInfo(team_id="england", name="England", group="L", elo=2000, champion_prob=0.1),
            TeamInfo(team_id="france", name="France", group="I", elo=2050, champion_prob=0.08),
        ],
        agent=agent,
    )


@pytest.fixture
def deps(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    deps.as_of = "2026-06-14"
    snapshot_dir = tmp_path / "snapshots" / "2026" / "06" / "13"
    snapshot_dir.mkdir(parents=True)
    agent = AgentBlock(
        narrative=NarrativeBlock(focus_story="Read yesterday's worlds", travel_memo="Travel is unchanged"),
        artifact_id="mixture-003",
        worlds=[WorldOut(name="market_base", weight=0.7, perturbations=[])],
    )
    agent_snapshot = _snapshot(
        run_id="agent-20260613-140248",
        created_at="2026-06-13T14:56:13+00:00",
        kind="agent",
        agent=agent,
    )
    live_snapshot = _snapshot(
        run_id="live-20260613-210542",
        created_at="2026-06-13T21:05:42+00:00",
        kind="live",
    )
    (snapshot_dir / "agent-20260613-140248.json").write_text(agent_snapshot.model_dump_json())
    (snapshot_dir / "live-20260613-210542.json").write_text(live_snapshot.model_dump_json())
    yield deps
    deps.runtime.shutdown()


async def test_previous_forecast_defaults_to_latest_agent_snapshot(deps):
    result = await _previous_forecast(PreviousForecastArgs(), deps)

    assert result.ok
    assert result.payload["run_id"] == "agent-20260613-140248"
    assert result.payload["kind"] == "agent"
    assert result.payload["worlds"][0]["name"] == "market_base"
    assert "artifact index missing" in result.payload["warnings"][0]


async def test_previous_forecast_can_read_latest_live_when_requested(deps):
    result = await _previous_forecast(PreviousForecastArgs(kind="live"), deps)

    assert result.ok
    assert result.payload["run_id"] == "live-20260613-210542"
    assert result.payload["kind"] == "live"
