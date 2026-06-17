from __future__ import annotations

from datetime import datetime

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import synthetic_state
from wolves.clients.api_football import FakeFixturesClient, MatchFixture
from wolves.config import Settings
from wolves.forecast import Forecaster
from wolves.live import live_pass
from wolves.run import generate_snapshot
from wolves.snapshot import AgentBlock, NarrativeBlock, Snapshot, WorldOut

DELTA = 0.3


def _finished_match_one() -> MatchFixture:
    return MatchFixture(
        fixture_id=1300001,
        kickoff=datetime.fromisoformat("2026-06-11T13:00:00-06:00"),
        status="finished",
        home="Mexico",
        away="South Africa",
        home_goals=2,
        away_goals=0,
    )


def _write_agent_snapshot(settings: Settings) -> None:
    base, _ = generate_snapshot(settings, n_sims=100, seed=3, run_id="agent-20260611-090000")
    agent = AgentBlock(
        narrative=NarrativeBlock(headline="Settled camp."),
        worlds=[
            WorldOut(
                name="keeper_fit",
                weight=1.0,
                perturbations=[{"team": "england", "delta": DELTA, "reason": "keeper fit"}],
            )
        ],
    )
    snapshot = base.model_copy(update={"run": base.run.model_copy(update={"kind": "agent"}), "agent": agent})
    snapshot_dir = settings.runs_root / "snapshots" / "2026" / "06" / "11"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "agent-20260611-090000.json").write_text(snapshot.model_dump_json())


def _forecaster(tmp_path) -> Forecaster:
    instance = Forecaster(Settings(runs_root=tmp_path, storage_mode="local"))
    instance._state = synthetic_state()
    return instance


async def test_live_pass_overlays_the_result_and_applies_the_published_worlds(tmp_path):
    settings = Settings(runs_root=tmp_path, storage_mode="local")
    _write_agent_snapshot(settings)
    fixtures = FakeFixturesClient(matches=[_finished_match_one()])

    assert await live_pass(settings, fixtures=fixtures, n_sims=400, seed=5, forecaster=_forecaster(tmp_path)) is True

    latest = Snapshot.model_validate_json((tmp_path / "snapshots" / "latest.json").read_text())
    assert latest.run.kind == "live"
    assert latest.run.run_id.startswith("live-")
    assert 1 not in {entry.match for entry in latest.matches}

    flat = _forecaster(tmp_path).sim_outputs(n_sims=400, seed=5)
    flat_england = next(t.champion_prob for t in flat.teams if t.team_id == "england")
    live_england = next(t.champion_prob for t in latest.teams if t.team_id == "england")
    assert live_england > flat_england
