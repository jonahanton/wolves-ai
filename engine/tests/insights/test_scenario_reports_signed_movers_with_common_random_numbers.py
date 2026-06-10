from __future__ import annotations

from wolves.forecast import StrengthPerturbation
from wolves.insights.scenario import run_scenario


def test_a_boost_moves_its_own_team_up_and_rivals_down(forecaster) -> None:
    result = run_scenario(
        forecaster, (StrengthPerturbation(team="england", delta=0.3, reason="test"),), n_sims=8000, seed=4
    )

    by_team = {d.team: d for d in result.title_movers}
    assert by_team["england"].delta_pp > 1.0
    # Individual rivals can gain from bracket reshuffles; in aggregate they lose.
    others = [d.delta_pp for t, d in by_team.items() if t != "england"]
    assert others and sum(others) < 0


def test_no_perturbation_means_no_movers(forecaster) -> None:
    result = run_scenario(forecaster, (), n_sims=8000, seed=4)
    assert result.title_movers == []
    assert result.r32_movers == []
