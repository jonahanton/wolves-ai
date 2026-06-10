from __future__ import annotations

import pytest

from wolves.quant.context import ContextArtifact
from wolves.quant.wolves_quant import _data, _state
from wolves.sim.format import FormatData, GroupMatch, KnockoutMatch, Team


@pytest.fixture(autouse=True)
def _fake_session(monkeypatch: pytest.MonkeyPatch):
    fmt = FormatData(
        teams=[
            Team(id="england", name="England", group="L", elo_code="EN"),
            Team(id="croatia", name="Croatia", group="L", elo_code="HR"),
        ],
        group_matches=[
            GroupMatch(match=1, group="L", date="2026-06-12", city="Dallas", home="england", away="croatia")
        ],
        knockout=[KnockoutMatch(match=73, stage="r32", date="2026-06-28", city="Dallas", home="1L", away="3:EHIJK")],
        venues=[],
    )
    state = type("S", (), {"teams": ["england", "croatia"], "strengths": [0.4, 0.2]})()
    fake_forecaster = type("F", (), {"fmt": fmt, "state": state})()
    monkeypatch.setattr(_state, "forecaster", lambda: fake_forecaster)
    artifacts = {
        "quant-001": ContextArtifact(
            id="quant-001",
            kind="quant",
            created_by="quant-baseline",
            summary="baseline digest",
            payload_path="/tmp/x.json",
            workspace_path="/tmp/ws",
        ),
        "evidence-001": ContextArtifact(
            id="evidence-001",
            kind="evidence",
            created_by="research",
            summary="keeper",
            payload_path="/tmp/y.json",
        ),
    }
    monkeypatch.setattr(_data, "context", lambda: type("C", (), {"artifacts": artifacts})())


def test_teams_join_groups_with_fitted_strengths():
    frame = _data.teams()
    assert list(frame["team"]) == ["england", "croatia"]
    assert frame.set_index("team").loc["croatia", "strength"] == 0.2
    assert frame.set_index("team").loc["england", "group"] == "L"


def test_fixtures_filter_by_team_across_group_and_knockout():
    all_rows = _data.fixtures()
    assert len(all_rows) == 2
    england = _data.fixtures(team="england")
    assert list(england["match"]) == [1]
    assert _data.fixtures(group="L")["stage"].tolist() == ["group"]


def test_artifacts_list_ids_kinds_and_workspaces():
    frame = _data.artifacts()
    assert list(frame["id"]) == ["evidence-001", "quant-001"]
    assert frame.set_index("id").loc["quant-001", "has_workspace"]
    assert not frame.set_index("id").loc["evidence-001", "has_workspace"]
