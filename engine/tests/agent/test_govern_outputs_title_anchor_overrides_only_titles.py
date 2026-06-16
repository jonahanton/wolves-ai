"""The title channel extremises away from title_anchor when one is given, while
the reach chains keep governing against the sim anchor. A regression here moves
published title numbers silently, so the two channels are pinned apart."""

from __future__ import annotations

from wolves.agent.forecast_artifact import govern_outputs
from wolves.sim.api import SimOutputs
from wolves.snapshot import FocusTeamBlock, TeamInfo


def _outputs(*, titles: dict[str, float], reach: float) -> SimOutputs:
    return SimOutputs(
        n_sims=1,
        seed=1,
        focus=FocusTeamBlock(
            team_id="a", group="A", finish_probs={"champion": titles["a"]}, reach_probs={"final": reach}, paths=[]
        ),
        slots=[],
        teams=[
            TeamInfo(team_id=team, name=team, group="A", elo=1800.0, champion_prob=p, reach_probs={"final": reach})
            for team, p in titles.items()
        ],
        groups=[],
        matches=[],
    )


def test_title_anchor_moves_titles_to_market_while_reach_tracks_sim():
    outputs = _outputs(titles={"a": 0.5, "b": 0.5}, reach=0.5)
    sim_anchor = _outputs(titles={"a": 0.9, "b": 0.1}, reach=0.9)
    market_anchor = {"a": 0.1, "b": 0.9}

    govern_outputs(outputs, sim_anchor, d=0.5, title_anchor=market_anchor)

    title_a = next(t.champion_prob for t in outputs.teams if t.team_id == "a")
    # Extremising toward the market anchor (0.1) pulls a's title below 0.5; had it
    # used the sim anchor (0.9) it would have risen instead.
    assert title_a < 0.5
    # Reach ignores title_anchor and governs toward the sim anchor (0.9), so it rises.
    assert outputs.focus.reach_probs["final"] > 0.5
