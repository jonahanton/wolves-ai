from __future__ import annotations

from types import SimpleNamespace

import pytest

from wolves.agent.dossier import _tournament
from wolves.config import Settings
from wolves.sim import results_store
from wolves.sim.format import FormatData, GroupMatch, KnockoutMatch, PlayedResult, Team


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
