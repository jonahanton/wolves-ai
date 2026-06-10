from __future__ import annotations

from wolves.sim.diff import diff_snapshots
from wolves.snapshot import Candidate, FocusTeamBlock, RunMeta, Slot, SlotSide, Snapshot, TeamInfo


def _snapshot(win_group: float, uzbekistan: float) -> Snapshot:
    return Snapshot(
        run=RunMeta(run_id="r", created_at="t", n_sims=1, engine_version="0.2.0", kind="sim_only"),
        focus=FocusTeamBlock(
            team_id="england",
            group="L",
            finish_probs={"win_group": win_group, "runner_up": 1.0 - win_group},
            reach_probs={"r32": 0.99},
            paths=[],
        ),
        slots=[
            Slot(
                match=80,
                stage="r32",
                date="d",
                city="Atlanta",
                home=SlotSide(label="1L", candidates=[Candidate(team_id="england", prob=win_group)]),
                away=SlotSide(label="3:EHIJK", candidates=[Candidate(team_id="uzbekistan", prob=uzbekistan)]),
            )
        ],
        teams=[TeamInfo(team_id="england", name="England", group="L", elo=2021.0, champion_prob=win_group / 7)],
    )


def test_identical_snapshots_diff_to_zero_moves():
    diff = diff_snapshots(_snapshot(0.65, 0.30), _snapshot(0.65, 0.30))
    assert diff.champion_deltas == {}
    assert diff.slot_deltas == []
    assert all(v == 0.0 for v in diff.finish_deltas.values())


def test_moves_above_threshold_are_reported_with_signed_deltas():
    diff = diff_snapshots(_snapshot(0.65, 0.30), _snapshot(0.60, 0.36))
    assert diff.finish_deltas["win_group"] == -0.05
    moved = {(d.match, d.side, d.team_id): d.delta for d in diff.slot_deltas}
    assert moved[(80, "away", "uzbekistan")] == 0.06
    assert moved[(80, "home", "england")] == -0.05
