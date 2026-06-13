"""The perturbation registry is the single source of truth: every entry
round-trips through the artifact parser, the publishes flag (not a hardcoded
type check) gates what-if instruments, and a brand-new type is reachable
end-to-end from its registry entry alone, with no edit to the parser, the wq
exports or the engine driver."""

from __future__ import annotations

from typing import ClassVar, Literal

import pytest
from pydantic import TypeAdapter

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import synthetic_state
from wolves.agent.forecast_artifact import ForecastArtifactError, worlds_from_payload
from wolves.config import Settings
from wolves.forecast import Forecaster
from wolves.sim import perturbations as perts
from wolves.sim.perturbations import (
    PERTURBATIONS,
    PerturbationSpec,
    StateContext,
    _Perturbation,
    parse_perturbation,
    spec_for,
)


@pytest.fixture()
def fitted_forecaster(tmp_path) -> Forecaster:
    fc = Forecaster(Settings(runs_root=tmp_path, storage_mode="local"))
    fc._state = synthetic_state()
    return fc


def test_every_registry_entry_round_trips_through_the_adapter():
    for spec in PERTURBATIONS:
        sample = _sample(spec.model)
        reparsed = parse_perturbation(sample.model_dump(mode="json"))
        assert spec_for(reparsed) is spec


def test_publishes_flag_gates_what_if_instruments():
    # Scoreline is the standing publishes=False type; it must be rejected by the
    # registry flag, not a name check.
    payload = {
        "weights": {"w": 1.0},
        "worlds": {"w": {"perturbations": [{"match": 5, "home_goals": 2, "away_goals": 1, "reason": "x"}]}},
    }
    with pytest.raises(ForecastArtifactError, match="never publish"):
        worlds_from_payload(payload)


def test_a_new_probe_type_is_reachable_from_its_registry_entry_alone(monkeypatch, fitted_forecaster):
    """Register a throwaway type touching only its own model and the registry
    tuple; it must parse, apply and move the simulation end-to-end."""

    class ProbeStrength(_Perturbation):
        name: ClassVar[str] = "probe_strength"
        type: Literal["probe_strength"] = "probe_strength"
        team: str
        bump: float

        def apply_to_state(self, ctx: StateContext) -> None:
            ctx.strengths[ctx.team_index[self.team]] += self.bump

    spec = PerturbationSpec(ProbeStrength, publishes=True)
    monkeypatch.setattr(perts, "PERTURBATIONS", (*PERTURBATIONS, spec))
    monkeypatch.setitem(perts._BY_NAME, spec.name, spec)
    monkeypatch.setattr(perts, "Perturbation", perts._union())
    monkeypatch.setattr(perts, "_ADAPTER", TypeAdapter(perts.Perturbation))

    fc = fitted_forecaster
    key = fc.state.teams[0]
    parsed = parse_perturbation({"type": "probe_strength", "team": key, "bump": 5.0, "reason": "probe"})
    assert isinstance(parsed, ProbeStrength)

    before = fc.title_probs(n_sims=4000, seed=0)
    after = fc.title_probs(n_sims=4000, seed=0, perturbations=(parsed,))
    # A large strength bump on one team must lift its title probability.
    assert after[key] > before[key]


def _sample(model: type[_Perturbation]) -> _Perturbation:
    name = model.name
    if name == "strength":
        return model(team="spain", delta=0.05, reason="x")
    if name in ("tempo", "home_advantage"):
        return model(delta=0.05, reason="x")
    if name == "match_rate":
        return model(match=1, home_goals_delta=0.1, reason="x")
    if name == "match_outcome":
        return model(match=1, p_home=0.5, p_draw=0.3, p_away=0.2, reason="x")
    if name == "scoreline":
        return model(match=1, home_goals=1, away_goals=0, reason="x")
    raise AssertionError(f"no sample for registry type {name!r}")
