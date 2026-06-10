from __future__ import annotations

import json
import math

import pytest

from wolves.agent.calibration import CalibrationLedger
from wolves.agent.scoring import score_yesterday
from wolves.config import Settings
from wolves.snapshot import (
    AgentBlock,
    FocusTeamBlock,
    MatchProbs,
    NarrativeBlock,
    RunMeta,
    Snapshot,
    WorldOut,
)


def _match(match: int, *, p_home: float, p_draw: float, p_away: float) -> MatchProbs:
    return MatchProbs(
        match=match,
        stage="group",
        date="2026-06-08T19:00:00Z",
        city="Mexico City",
        home_id="mexico",
        away_id="south-africa",
        p_home=p_home,
        p_draw=p_draw,
        p_away=p_away,
    )


def _snapshot(*, run_id: str, created_at: str, kind: str, matches: list[MatchProbs], agent: AgentBlock | None = None):
    return Snapshot(
        run=RunMeta(run_id=run_id, created_at=created_at, n_sims=1000, engine_version="0.2.0", kind=kind),
        focus=FocusTeamBlock(team_id="england", group="L", finish_probs={}, reach_probs={}, paths=[]),
        slots=[],
        teams=[],
        matches=matches,
        agent=agent,
    )


@pytest.fixture
def settings(tmp_path) -> Settings:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "results.json").write_text(
        json.dumps({"results": [{"match": 1, "homeGoals": 2, "awayGoals": 0}]})
    )
    runs_root = tmp_path / "runs"
    snapshot_dir = runs_root / "snapshots" / "2026" / "06" / "08"
    snapshot_dir.mkdir(parents=True)

    baseline = _snapshot(
        run_id="run-20260608",
        created_at="2026-06-08T06:00:00+00:00",
        kind="sim_only",
        matches=[_match(1, p_home=0.5, p_draw=0.3, p_away=0.2)],
    )
    agent = AgentBlock(
        narrative=NarrativeBlock(focus_story="story", travel_memo="memo"),
        worlds=[
            WorldOut(
                name="mexico_altitude",
                weight=1.0,
                perturbations=[{"team": "mexico", "delta": 0.05, "reason": "altitude"}],
            )
        ],
    )
    previous = _snapshot(
        run_id="agent-20260608-120000",
        created_at="2026-06-08T12:00:00+00:00",
        kind="agent",
        matches=[
            _match(1, p_home=0.6, p_draw=0.25, p_away=0.15),
            _match(2, p_home=0.4, p_draw=0.3, p_away=0.3),
            MatchProbs(
                match=80,
                stage="r32",
                date="2026-06-28T19:00:00Z",
                city="Atlanta",
                home_id="england",
                away_id="ghana",
                p_home=0.8,
                p_away=0.2,
                p_decided_90=0.7,
                p_pairing=0.3,
            ),
        ],
        agent=agent,
    )
    (snapshot_dir / "run-20260608.json").write_text(baseline.model_dump_json())
    (snapshot_dir / "agent-20260608-120000.json").write_text(previous.model_dump_json())
    (runs_root / "snapshots" / "latest.json").write_text(previous.model_dump_json())

    return Settings(data_dir=tmp_path / "data", runs_root=runs_root)


def test_resolved_group_match_is_scored_against_all_baselines(settings):
    summary = score_yesterday(settings, as_of="2026-06-09", run_id="agent-20260609-000000")

    scores = CalibrationLedger(settings.calibration_path).scores()
    assert [s.match_id for s in scores] == ["1"]
    score = scores[0]
    assert score.outcome == "home"
    assert set(score.brier) == {"model", "uniform", "frozen_sim"}
    assert score.brier["model"] < score.brier["frozen_sim"] < score.brier["uniform"]
    assert "Brier model" in summary


def test_adjusted_match_records_log_loss_pnl_versus_frozen_sim(settings):
    score_yesterday(settings, as_of="2026-06-09", run_id="agent-20260609-000000")
    score = CalibrationLedger(settings.calibration_path).scores()[0]
    assert score.adjustment_pnl == pytest.approx(math.log(0.6) - math.log(0.5))


def test_summary_lands_in_lessons_and_rescoring_does_not_duplicate(settings):
    first = score_yesterday(settings, as_of="2026-06-09", run_id="agent-20260609-000000")
    assert first
    assert first in settings.lessons_path.read_text()

    second = score_yesterday(settings, as_of="2026-06-09", run_id="agent-20260609-000001")
    assert second == ""
    assert len(CalibrationLedger(settings.calibration_path).scores()) == 1


def test_unresolved_and_knockout_entries_are_not_scored(settings):
    score_yesterday(settings, as_of="2026-06-09", run_id="agent-20260609-000000")
    match_ids = {s.match_id for s in CalibrationLedger(settings.calibration_path).scores()}
    assert "2" not in match_ids
    assert "80" not in match_ids
