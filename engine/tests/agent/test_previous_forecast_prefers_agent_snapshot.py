from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.agent.tools.memory.forecast_history import ForecastHistoryArgs, _forecast_history
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


def _snapshot(
    *,
    run_id: str,
    created_at: str,
    kind: str,
    agent: AgentBlock | None = None,
    as_of: str = "2026-06-13",
) -> Snapshot:
    return Snapshot(
        run=RunMeta(
            run_id=run_id,
            created_at=created_at,
            as_of=as_of,
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
        narrative=NarrativeBlock(headline="Read yesterday's worlds"),
        artifact_id="mixture-003",
        worlds=[WorldOut(name="market_base", weight=0.7, perturbations=[])],
        branch_audit={
            "verdict": "France branch merged into market base.",
            "checks": [{"key": "france-market-premium", "status": "merged_into_base"}],
        },
        world_metadata={"market_base": {"label": "Market view", "summary": "Odds-implied strengths."}},
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
    assert result.payload["published_distribution"]["worlds"][0]["name"] == "market_base"
    assert result.payload["branch_audit"]["checks"][0]["key"] == "france-market-premium"
    assert result.payload["world_metadata"]["market_base"]["label"] == "Market view"
    assert result.payload["artifact_index_available"] is False
    assert "artifact index missing" in result.payload["warnings"][0]


async def test_backfilled_older_snapshot_does_not_beat_newer_forecast_day(deps):
    snapshot_dir = deps.settings.runs_root / "snapshots" / "2026" / "06" / "12"
    snapshot_dir.mkdir(parents=True)
    backfilled = _snapshot(
        run_id="agent-20260612-backfill",
        created_at="2026-06-15T09:00:00+00:00",
        kind="agent",
        as_of="2026-06-12",
        agent=AgentBlock(narrative=NarrativeBlock(headline="Older backfill"), artifact_id="mixture-old"),
    )
    (snapshot_dir / "agent-20260612-backfill.json").write_text(backfilled.model_dump_json())

    result = await _previous_forecast(PreviousForecastArgs(), deps)

    assert result.ok
    assert result.payload["run_id"] == "agent-20260613-140248"
    assert [run["run_id"] for run in result.payload["recent_runs"][:2]] == [
        "agent-20260613-140248",
        "agent-20260612-backfill",
    ]


async def test_previous_forecast_can_be_disabled_for_scratch_run(deps):
    deps.disable_continuity = True

    result = await _previous_forecast(PreviousForecastArgs(), deps)

    assert not result.ok
    assert result.error is not None
    assert result.error.type == "not_found"
    assert "disabled" in result.error.message


async def test_forecast_history_can_be_disabled_for_scratch_run(deps):
    deps.disable_continuity = True

    result = await _forecast_history(ForecastHistoryArgs(team="england"), deps)

    assert result.ok
    assert result.payload == {"team": "england", "series": []}


def test_previous_forecast_schema_does_not_advertise_live_snapshots():
    with pytest.raises(ValidationError):
        PreviousForecastArgs.model_validate({"kind": "live"})


async def test_previous_forecast_rejects_live_run_ids(deps):
    result = await _previous_forecast(PreviousForecastArgs(run_id="live-20260613-210542"), deps)

    assert not result.ok
    assert result.error is not None
    assert result.error.type == "invalid_arguments"
    assert "only opens agent forecasts" in result.error.message


async def test_previous_forecast_rejects_future_agent_run_id(deps):
    snapshot_dir = deps.settings.runs_root / "snapshots" / "2026" / "06" / "15"
    snapshot_dir.mkdir(parents=True)
    future = _snapshot(
        run_id="agent-20260615-090000",
        created_at="2026-06-15T09:00:00+00:00",
        kind="agent",
        as_of="2026-06-15",
    )
    (snapshot_dir / "agent-20260615-090000.json").write_text(future.model_dump_json())

    result = await _previous_forecast(PreviousForecastArgs(run_id="agent-20260615-090000"), deps)

    assert not result.ok
    assert result.error is not None
    assert result.error.type == "not_found"


async def test_previous_forecast_recent_runs_are_point_in_time(deps):
    snapshot_dir = deps.settings.runs_root / "snapshots" / "2026" / "06" / "15"
    snapshot_dir.mkdir(parents=True)
    future = _snapshot(
        run_id="agent-20260615-090000",
        created_at="2026-06-15T09:00:00+00:00",
        kind="agent",
        as_of="2026-06-15",
    )
    (snapshot_dir / "agent-20260615-090000.json").write_text(future.model_dump_json())

    result = await _previous_forecast(PreviousForecastArgs(), deps)

    assert result.ok
    assert [run["run_id"] for run in result.payload["recent_runs"]] == ["agent-20260613-140248"]


async def test_previous_forecast_exposes_continuity_digest(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    deps.as_of = "2026-06-14"
    run_id = "agent-20260613-140248"
    snapshot_dir = tmp_path / "snapshots" / "2026" / "06" / "13"
    snapshot_dir.mkdir(parents=True)
    agent = AgentBlock(
        narrative=NarrativeBlock(headline="Prior forecast"),
        artifact_id="mixture-001",
        worlds=[WorldOut(name="market_base", weight=0.7, perturbations=[])],
    )
    snapshot = _snapshot(
        run_id=run_id,
        created_at="2026-06-13T14:56:13+00:00",
        kind="agent",
        agent=agent,
    )
    (snapshot_dir / f"{run_id}.json").write_text(snapshot.model_dump_json())
    store = build_run_store(tmp_path, run_id=run_id)
    store.add(
        kind="retrieval",
        created_by="research-news",
        summary="ranked team news sources",
        payload={
            "sub_question": "fresh contender news",
            "rankings": [
                {
                    "url": "https://www.reuters.com/sports/soccer/france",
                    "title": "France squad update",
                    "score": 0.91,
                    "reason": "direct squad reporting",
                }
            ],
        },
    )
    (tmp_path / "runs" / run_id / "events.jsonl").write_text(
        "\n".join(
            [
                '{"kind":"graph_patch","summary":"wave 1: 1 op(s)"}',
                '{"kind":"web_search","summary":"brave search"}',
                '{"kind":"quant_exec","summary":"exec analysis_001.py -> ok"}',
                '{"kind":"validation","summary":"submission accepted"}',
            ]
        )
        + "\n"
    )

    result = await _previous_forecast(PreviousForecastArgs(), deps)
    deps.runtime.shutdown()

    assert result.ok
    digest = result.payload["continuity_digest"]
    assert digest["events"]["web_searches"] == 1
    assert digest["events"]["quant_execs"] == 1
    assert digest["artifacts"]["counts"]["retrieval"] == 1
    assert "audit trail" in result.payload["continuity_summary"]
    assert "template" in result.payload["continuity_summary"]
