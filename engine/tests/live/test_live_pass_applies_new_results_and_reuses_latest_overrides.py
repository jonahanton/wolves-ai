from __future__ import annotations

from datetime import datetime

import pytest

from wolves.clients.api_football import FakeFixturesClient, MatchFixture
from wolves.config import Settings
from wolves.live import live_pass
from wolves.run import generate_snapshot
from wolves.sim.api import run_simulation
from wolves.snapshot import AgentBlock, NarrativeBlock, RatingOverrideOut, Snapshot

DELTA = 25.0


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
    base = generate_snapshot(settings, n_sims=100, seed=3, run_id="agent-20260611-090000")
    agent = AgentBlock(
        narrative=NarrativeBlock(england_story="Settled camp.", travel_memo="East coast if they win the group."),
        rating_overrides=[RatingOverrideOut(team_id="england", delta_elo=DELTA, cause="keeper fit")],
    )
    snapshot = base.model_copy(update={"run": base.run.model_copy(update={"kind": "agent"}), "agent": agent})
    settings.runs_root.mkdir(parents=True, exist_ok=True)
    (settings.runs_root / "agent-20260611-090000.json").write_text(snapshot.model_dump_json())


async def test_live_pass_overlays_the_result_and_applies_the_agent_override(tmp_path):
    settings = Settings(runs_root=tmp_path)
    _write_agent_snapshot(settings)
    fixtures = FakeFixturesClient(matches=[_finished_match_one()])

    assert await live_pass(settings, fixtures=fixtures, n_sims=150, seed=5) is True

    latest = Snapshot.model_validate_json((tmp_path / "latest.json").read_text())
    assert latest.run.kind == "live"
    assert latest.run.run_id.startswith("live-")
    assert 1 not in {entry.match for entry in latest.matches}

    baseline = run_simulation({}, {}, 100, 1)
    base_rating = next(t.rating for t in baseline.teams if t.team_id == "england")
    live_rating = next(t.rating for t in latest.teams if t.team_id == "england")
    assert live_rating == pytest.approx(base_rating + DELTA, abs=0.1)
