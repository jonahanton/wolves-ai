from __future__ import annotations

from wolves.live import publishable_results
from wolves.sim.format import PlayedResult
from wolves.snapshot import MatchProbs, RunMeta, Snapshot


def test_persisted_result_remains_publishable_until_latest_snapshot_contains_it() -> None:
    previous = Snapshot(
        run=RunMeta(
            run_id="run-20260611",
            created_at="2026-06-11T10:00:00+00:00",
            n_sims=10,
            engine_version="x",
            kind="sim_only",
        ),
        focus={"team_id": "england", "group": "L", "finish_probs": {}, "reach_probs": {}, "paths": []},
        slots=[],
        teams=[],
        matches=[
            MatchProbs(
                match=1,
                stage="group",
                date="2026-06-11",
                city="Mexico City",
                home_id="mexico",
                away_id="south_africa",
                p_home=0.5,
                p_draw=0.3,
                p_away=0.2,
            )
        ],
    )
    result = PlayedResult(match=1, home_goals=2, away_goals=0)

    pending = publishable_results({1: result}, file_results={1: result}, previous=previous)

    assert pending == {1: result}
