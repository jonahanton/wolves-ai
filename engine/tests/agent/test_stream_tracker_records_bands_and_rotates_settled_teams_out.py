from __future__ import annotations

import pytest

from wolves.agent.stream import load_stream, record_stream
from wolves.config import Settings
from wolves.snapshot import (
    DistributionsBlock,
    FocusTeamBlock,
    RunMeta,
    Snapshot,
    TeamDistributions,
    TeamInfo,
)

LEVELS = [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95]
TEAMS = [
    ("france", 0.20),
    ("brazil", 0.18),
    ("england", 0.15),
    ("spain", 0.12),
    ("argentina", 0.10),
    ("germany", 0.08),
    ("portugal", 0.06),
    ("netherlands", 0.05),
    ("italy", 0.03),
    ("croatia", 0.02),
]


def _snapshot(*, run_id: str, as_of: str, settled: set[str] = frozenset()) -> Snapshot:
    teams = [
        TeamInfo(team_id=team, name=team.title(), group="A", elo=1800.0, champion_prob=prob) for team, prob in TEAMS
    ]
    distributions = DistributionsBlock(
        quantile_levels=LEVELS,
        teams={
            team: (
                TeamDistributions(settled={"champion": 0})
                if team in settled
                else TeamDistributions(quantiles={"champion": [prob * f for f in (0.5, 0.6, 0.8, 1.0, 1.2, 1.4, 1.5)]})
            )
            for team, prob in TEAMS
        },
    )
    return Snapshot(
        run=RunMeta(
            run_id=run_id,
            created_at=f"{as_of}T06:00:00+00:00",
            as_of=as_of,
            n_sims=1000,
            engine_version="0.2.0",
            kind="agent",
        ),
        focus=FocusTeamBlock(team_id="england", group="L", finish_probs={}, reach_probs={}, paths=[]),
        slots=[],
        teams=teams,
        distributions=distributions,
    )


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(runs_root=tmp_path / "runs")


def test_records_carry_bands_for_focus_and_top_teams(settings):
    record_stream(settings, _snapshot(run_id="run-1", as_of="2026-06-12"))
    rows = load_stream(settings)
    assert [r.team for r in rows] == [team for team, _ in TEAMS[:8]]
    france = rows[0]
    assert france.mean == pytest.approx(0.20)
    assert france.q10 == pytest.approx(0.20 * 0.6)
    assert france.q90 == pytest.approx(0.20 * 1.4)
    assert all(r.run_id == "run-1" and r.as_of == "2026-06-12" for r in rows)


def test_settled_team_rotates_out_for_the_next_largest_open_team(settings):
    record_stream(settings, _snapshot(run_id="run-1", as_of="2026-06-12"))
    record_stream(settings, _snapshot(run_id="run-2", as_of="2026-06-13", settled={"brazil"}))
    day_two = [r.team for r in load_stream(settings) if r.run_id == "run-2"]
    assert "brazil" not in day_two
    assert "italy" in day_two


def test_missing_distributions_block_records_null_bands_and_rerecording_is_idempotent(settings):
    snapshot = _snapshot(run_id="run-1", as_of="2026-06-12")
    snapshot.distributions = None
    record_stream(settings, snapshot)
    record_stream(settings, snapshot)
    rows = load_stream(settings)
    assert len(rows) == 8
    assert all(r.q10 is None and r.q90 is None for r in rows)
