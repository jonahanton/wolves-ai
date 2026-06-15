from __future__ import annotations

from tests.graph.conftest import build_graph_deps
from wolves.agent.tools.memory.forecast_history import ForecastHistoryArgs, _champion_band, _forecast_history
from wolves.snapshot import (
    DistributionsBlock,
    FocusTeamBlock,
    RunMeta,
    Snapshot,
    TeamDistributions,
    TeamInfo,
)


def _snapshot(*, with_block: bool) -> Snapshot:
    distributions = None
    if with_block:
        distributions = DistributionsBlock(
            quantile_levels=[0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95],
            teams={"england": TeamDistributions(quantiles={"champion": [0.05, 0.06, 0.08, 0.1, 0.12, 0.14, 0.15]})},
        )
    return Snapshot(
        run=RunMeta(
            run_id="agent-20260612-000000",
            created_at="2026-06-12T08:00:00+00:00",
            n_sims=100,
            engine_version="0",
            kind="agent",
        ),
        focus=FocusTeamBlock(team_id="england", group="L", finish_probs={}, reach_probs={}, paths=[]),
        slots=[],
        teams=[TeamInfo(team_id="england", name="England", group="L", elo=2000.0)],
        distributions=distributions,
    )


def test_forecast_history_carries_band_fields() -> None:
    assert _champion_band(_snapshot(with_block=True), "england") == (0.06, 0.14)
    assert _champion_band(_snapshot(with_block=False), "england") is None
    assert _champion_band(_snapshot(with_block=True), "spain") is None


async def test_forecast_history_defaults_to_agent_runs(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.as_of = "2026-06-15"
    snapshot_dir = tmp_path / "snapshots" / "2026" / "06" / "13"
    snapshot_dir.mkdir(parents=True)
    for run_id, kind, p_title in (
        ("agent-20260613-140248", "agent", 0.08),
        ("live-20260613-210542", "live", 0.11),
        ("agent-20260615-101351", "agent", 0.12),
    ):
        snapshot = _snapshot(with_block=False)
        snapshot.run.run_id = run_id
        snapshot.run.kind = kind
        snapshot.run.as_of = "2026-06-15" if run_id.endswith("101351") else "2026-06-13"
        snapshot.run.created_at = f"{snapshot.run.as_of}T{'14:00:00' if kind == 'agent' else '21:00:00'}+00:00"
        snapshot.teams[0].champion_prob = p_title
        (snapshot_dir / f"{run_id}.json").write_text(snapshot.model_dump_json())

    result = await _forecast_history(ForecastHistoryArgs(team="england"), deps)
    deps.runtime.shutdown()

    assert [point["run_id"] for point in result.payload["series"]] == ["agent-20260613-140248"]


async def test_forecast_history_sorts_backfills_by_forecast_day(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.as_of = "2026-06-15"
    snapshot_dir = tmp_path / "snapshots" / "2026" / "06" / "13"
    snapshot_dir.mkdir(parents=True)
    for run_id, as_of, created_at, p_title in (
        ("agent-20260612-backfill", "2026-06-12", "2026-06-15T09:00:00+00:00", 0.07),
        ("agent-20260613-140248", "2026-06-13", "2026-06-13T14:00:00+00:00", 0.08),
    ):
        snapshot = _snapshot(with_block=False)
        snapshot.run.run_id = run_id
        snapshot.run.as_of = as_of
        snapshot.run.created_at = created_at
        snapshot.teams[0].champion_prob = p_title
        (snapshot_dir / f"{run_id}.json").write_text(snapshot.model_dump_json())

    result = await _forecast_history(ForecastHistoryArgs(team="england"), deps)
    deps.runtime.shutdown()

    assert [point["run_id"] for point in result.payload["series"]] == [
        "agent-20260612-backfill",
        "agent-20260613-140248",
    ]
