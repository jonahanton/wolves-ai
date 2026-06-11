from __future__ import annotations

import pytest

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import synthetic_state
from wolves.config import Settings
from wolves.forecast import (
    Forecaster,
    MatchRatePerturbation,
    ScorelinePerturbation,
    UnboundMatchPerturbationError,
)


@pytest.fixture()
def forecaster(tmp_path) -> Forecaster:
    instance = Forecaster(Settings(runs_root=tmp_path, storage_mode="local"))
    instance._state = synthetic_state()
    return instance


def _fixture_teams(forecaster: Forecaster) -> tuple[int, str, str]:
    spec = forecaster.fmt.group_matches[0]
    return spec.match, spec.home, spec.away


def test_refuses_match_keyed_perturbations_without_a_match_id(forecaster: Forecaster):
    match, home, away = _fixture_teams(forecaster)
    perturbation = MatchRatePerturbation(match=match, home_goals_delta=-0.5, reason="heat")

    with pytest.raises(UnboundMatchPerturbationError) as err:
        forecaster.match_probs(home, away, perturbations=(perturbation,))
    assert match in err.value.matches


def test_binds_rate_offsets_when_the_match_id_is_given(forecaster: Forecaster):
    match, home, away = _fixture_teams(forecaster)
    perturbation = MatchRatePerturbation(match=match, home_goals_delta=-0.8, reason="heat")

    unperturbed = forecaster.match_probs(home, away)
    bound = forecaster.match_probs(home, away, perturbations=(perturbation,), match=match)

    assert bound["home"] < unperturbed["home"]
    other_match = forecaster.fmt.group_matches[1].match
    elsewhere = forecaster.match_probs(home, away, perturbations=(perturbation,), match=other_match)
    assert elsewhere == pytest.approx(unperturbed)


def test_pinned_scoreline_binds_as_a_point_mass(forecaster: Forecaster):
    match, home, away = _fixture_teams(forecaster)
    pinned = ScorelinePerturbation(match=match, home_goals=2, away_goals=0, reason="what if")

    probs = forecaster.match_probs(home, away, perturbations=(pinned,), match=match)
    assert probs == {"home": 1.0, "draw": 0.0, "away": 0.0}
