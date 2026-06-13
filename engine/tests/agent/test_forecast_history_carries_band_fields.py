from __future__ import annotations

from wolves.agent.tools.memory.forecast_history import _champion_band
from wolves.snapshot import (
    DistributionsBlock,
    FocusTeamBlock,
    RunMeta,
    Snapshot,
    TeamDistributions,
    TeamInfo,
)


def _snapshot(*, with_block: bool) -> Snapshot:
    distributions = None
    if with_block:
        distributions = DistributionsBlock(
            quantile_levels=[0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95],
            teams={"england": TeamDistributions(quantiles={"champion": [0.05, 0.06, 0.08, 0.1, 0.12, 0.14, 0.15]})},
        )
    return Snapshot(
        run=RunMeta(
            run_id="agent-20260612-000000",
            created_at="2026-06-12T08:00:00+00:00",
            n_sims=100,
            engine_version="0",
            kind="agent",
        ),
        focus=FocusTeamBlock(team_id="england", group="L", finish_probs={}, reach_probs={}, paths=[]),
        slots=[],
        teams=[TeamInfo(team_id="england", name="England", group="L", elo=2000.0)],
        distributions=distributions,
    )


def test_forecast_history_carries_band_fields() -> None:
    assert _champion_band(_snapshot(with_block=True), "england") == (0.06, 0.14)
    assert _champion_band(_snapshot(with_block=False), "england") is None
    assert _champion_band(_snapshot(with_block=True), "spain") is None
