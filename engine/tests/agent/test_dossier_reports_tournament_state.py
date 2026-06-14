from __future__ import annotations

from types import SimpleNamespace

import pytest

from wolves.agent.dossier import _published, _tournament
from wolves.config import Settings
from wolves.sim import results_store
from wolves.sim.format import FormatData, GroupMatch, KnockoutMatch, PlayedResult, Team
from wolves.snapshot import AgentBlock, FocusTeamBlock, NarrativeBlock, RunMeta, Snapshot, TeamInfo, WorldOut


@pytest.fixture
def deps(tmp_path):
    fmt = FormatData(
        teams=[
            Team(id="england", name="England", group="L", elo_code="EN"),
            Team(id="croatia", name="Croatia", group="L", elo_code="HR"),
            Team(id="ghana", name="Ghana", group="L", elo_code="GH"),
        ],
        group_matches=[
            GroupMatch(match=1, group="L", date="2026-06-11", city="Dallas", home="england", away="croatia"),
            GroupMatch(match=2, group="L", date="2026-06-13", city="Dallas", home="ghana", away="croatia"),
        ],
        knockout=[KnockoutMatch(match=73, stage="r32", date="2026-06-28", city="Dallas", home="1L", away="3:EHIJK")],
        venues=[],
    )
    return SimpleNamespace(
        forecaster=SimpleNamespace(fmt=fmt),
        settings=Settings(runs_root=tmp_path, storage_mode="local"),
        as_of="2026-06-12",
    )


def test_standings_score_three_one_zero_and_upcoming_fixtures_listed(deps, monkeypatch):
    monkeypatch.setattr(
        results_store, "persisted_results", lambda settings: {1: PlayedResult(match=1, home_goals=2, away_goals=2)}
    )

    section = _tournament(deps, None)

    assert "1 played" in section
    assert "L: croatia 1, england 1" in section or "L: england 1, croatia 1" in section
    assert "m2 ghana v croatia (2026-06-13)" in section
    assert "m73" not in section


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
        focus=FocusTeamBlock(team_id="england", group="L", finish_probs={}, reach_probs={}, paths=[]),
        slots=[],
        teams=[
            TeamInfo(team_id="england", name="England", group="L", elo=2000, champion_prob=0.1),
            TeamInfo(team_id="france", name="France", group="I", elo=2050, champion_prob=0.08),
        ],
        agent=agent,
    )


def test_previous_anchor_prefers_agent_snapshot_over_later_live(tmp_path):
    snapshot_dir = tmp_path / "snapshots" / "2026" / "06" / "13"
    snapshot_dir.mkdir(parents=True)
    agent = AgentBlock(
        narrative=NarrativeBlock(focus_story="story", travel_memo="memo"),
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
    deps = SimpleNamespace(
        settings=Settings(_env_file=None, runs_root=tmp_path, storage_mode="local"),
        as_of="2026-06-14",
    )

    section = _published(deps, None)

    assert "Previous agent forecast (agent-20260613-140248" in section
    assert "Its worlds: market_base 0.70" in section
    assert "Latest live snapshot is live-20260613-210542" in section
