from __future__ import annotations

import numpy as np

from wolves.config import Settings
from wolves.sidecars import SidecarInputs, locked_knockout_pairings
from wolves.sim.format import load_format
from wolves.sim.mc import KnockoutTieStats, SimResult


def _result(stats: dict[int, KnockoutTieStats]) -> SimResult:
    empty = np.zeros(0)
    return SimResult(
        n_sims=1,
        rank_in_group=empty,
        third_qualified=empty,
        group_points=empty,
        group_goals={},
        ko_home={},
        ko_away={},
        ko_winner={},
        ko_loser={},
        ko_stats=stats,
    )


def _stats(home: int, away: int, p_pairing: float) -> KnockoutTieStats:
    return KnockoutTieStats(
        home=home, away=away, p_pairing=p_pairing, p_home_win=0.5, p_decided_90=0.7, modal_score=(1, 0)
    )


def _inputs(fmt, per_world, played) -> SidecarInputs:
    return SidecarInputs(
        fmt=fmt,
        per_world_results=per_world,
        weights={name: 1.0 / len(per_world) for name in per_world},
        parameter_draws=1,
        rng_seed=0,
        forecaster=None,  # type: ignore[arg-type]
        world_specs={name: ((), ()) for name in per_world},
        wdl_curve_draws=1,
        played=played,
    )


def test_only_unplayed_ties_agreed_across_worlds_at_near_certainty_are_listed() -> None:
    fmt = load_format(Settings().data_dir)
    r32 = [m.match for m in fmt.knockout if m.stage == "r32"]
    fixed, weak, disputed, done = r32[0], r32[1], r32[2], r32[3]

    common = {fixed: _stats(0, 1, 1.0), weak: _stats(2, 3, 0.4), done: _stats(6, 7, 1.0)}
    per_world = {
        "a": _result({**common, disputed: _stats(4, 5, 1.0)}),
        "b": _result({**common, disputed: _stats(5, 4, 1.0)}),
    }
    pairings = locked_knockout_pairings(_inputs(fmt, per_world, frozenset({done})))

    assert pairings == {fixed: (fmt.teams[0].id, fmt.teams[1].id)}
