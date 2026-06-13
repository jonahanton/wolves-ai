"""The conditional perturbation types each move the quantity they are scored
on: a knockout-outcome bet shifts the pairing's resolved advance, and the
opponent- and stage-conditional shifts move the targeted team's title share."""

from __future__ import annotations

import pytest

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import synthetic_state
from wolves.config import Settings
from wolves.forecast import (
    Forecaster,
    KnockoutOutcome,
    OpponentConditionalStrength,
    StageConditionalStrength,
)

N_SIMS = 8000
SEED = 0
# Two dominant teams so the pairing reliably occurs deep in the bracket.
FAVOURITE = "spain"
RIVAL = "argentina"


@pytest.fixture()
def forecaster(tmp_path) -> Forecaster:
    fc = Forecaster(Settings(runs_root=tmp_path, storage_mode="local"))
    fc._state = synthetic_state({FAVOURITE: 1.2, RIVAL: 1.0})
    return fc


def _title(fc: Forecaster, team: str, perturbations=()) -> float:
    return fc.title_probs(n_sims=N_SIMS, seed=SEED, perturbations=perturbations)[team]


def test_knockout_outcome_lifts_the_backed_team_and_suppresses_the_opponent(forecaster: Forecaster):
    base_fav, base_rival = _title(forecaster, FAVOURITE), _title(forecaster, RIVAL)
    bet = KnockoutOutcome(team=FAVOURITE, opponent=RIVAL, p_advance=0.99, reason="x")
    assert _title(forecaster, FAVOURITE, (bet,)) > base_fav
    assert _title(forecaster, RIVAL, (bet,)) < base_rival


def test_opponent_conditional_strength_lifts_a_team_against_named_rivals(forecaster: Forecaster):
    shift = OpponentConditionalStrength(team=FAVOURITE, opponents=[RIVAL], delta=0.8, reason="x")
    assert _title(forecaster, FAVOURITE, (shift,)) > _title(forecaster, FAVOURITE)


def test_stage_conditional_strength_lifts_a_team_in_the_named_round(forecaster: Forecaster):
    shift = StageConditionalStrength(team=FAVOURITE, stage="final", delta=0.8, reason="x")
    assert _title(forecaster, FAVOURITE, (shift,)) > _title(forecaster, FAVOURITE)


def test_alias_named_team_resolves_to_its_column(tmp_path):
    # USA's fmt id differs from its dataset slug; the in-match resolver must
    # still bind it, or the perturbation silently no-ops.
    fc = Forecaster(Settings(runs_root=tmp_path, storage_mode="local"))
    fc._state = synthetic_state({"united-states": 1.2, RIVAL: 1.0})
    shift = OpponentConditionalStrength(team="USA", opponents=[RIVAL], delta=0.8, reason="x")
    assert _title(fc, "usa", (shift,)) > _title(fc, "usa")
