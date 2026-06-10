from __future__ import annotations

import json
from pathlib import Path

import pytest

from wolves.forecast import StrengthPerturbation
from wolves.quant.wolves_quant import _mixture
from wolves.quant.wolves_quant._mixture import (
    Factor,
    MixtureSizeError,
    MixtureWeightError,
    Scenario,
    scenario_mixture,
)
from wolves.quant.wolves_quant._state import SESSION

EFFECTS = {"plays": 0.07, "misses": 0.06, "normal": 0.0, "heat": -0.01}


@pytest.fixture(autouse=True)
def _fake_sim(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """World probabilities become the sum of named effects, so the lattice
    arithmetic is checkable without a fitted model."""

    def fake_simulate(perturbations=(), *, n_sims=None, seed=0):
        return {"england": round(sum(EFFECTS[p.reason] for p in perturbations), 6)}

    monkeypatch.setattr(_mixture, "simulate", fake_simulate)
    monkeypatch.setattr(_mixture, "baseline", lambda *, n_sims=None, seed=0: {"england": 0.07})
    monkeypatch.setattr(_mixture, "noise_floor", lambda *, n_sims=None, seed=0: 0.17)
    monkeypatch.setattr(_mixture, "context", lambda: type("C", (), {"default_n_sims": 1000})())
    monkeypatch.setattr(SESSION, "root", tmp_path)


def _variant(name: str, weight: float) -> Scenario:
    return Scenario(
        name=name,
        weight=weight,
        perturbations=[StrengthPerturbation(team="england", delta=0.0, reason=name)],
    )


def _factors() -> list[Factor]:
    return [
        Factor(name="saka", variants=[_variant("plays", 0.6), _variant("misses", 0.4)]),
        Factor(name="weather", variants=[_variant("normal", 0.7), _variant("heat", 0.3)]),
    ]


def test_factor_product_enumerates_marginals_and_persists(tmp_path: Path):
    out = scenario_mixture(factors=_factors(), name="mixture_saka")

    expected = 0.6 * 0.7 * 0.07 + 0.6 * 0.3 * 0.06 + 0.4 * 0.7 * 0.06 + 0.4 * 0.3 * 0.05
    assert out["mixture"]["england"] == pytest.approx(expected)
    assert set(out["weights"]) == {"plays|normal", "plays|heat", "misses|normal", "misses|heat"}
    assert out["weights"]["misses|heat"] == pytest.approx(0.12)
    saka_marginal = out["marginals"]["saka"]
    assert saka_marginal["plays"]["england"] == pytest.approx(0.7 * 0.07 + 0.3 * 0.06)
    assert out["noise_floor_pp"] == 0.17

    persisted = json.loads((tmp_path / "outputs" / "mixture_saka.json").read_text(encoding="utf-8"))
    assert persisted["mixture"]["england"] == pytest.approx(expected)


def test_joint_table_reweights_the_same_lattice():
    independent = scenario_mixture(factors=_factors(), name="m1")
    joint = {"plays|normal": 0.5, "plays|heat": 0.1, "misses|normal": 0.2, "misses|heat": 0.2}
    correlated = scenario_mixture(factors=_factors(), joint=joint, name="m2")

    assert correlated["conditionals"] == independent["conditionals"]
    expected = 0.5 * 0.07 + 0.1 * 0.06 + 0.2 * 0.06 + 0.2 * 0.05
    assert correlated["mixture"]["england"] == pytest.approx(expected)


def test_weight_and_size_errors():
    bad = [Factor(name="saka", variants=[_variant("plays", 0.6), _variant("misses", 0.3)])]
    with pytest.raises(MixtureWeightError):
        scenario_mixture(factors=bad)

    wide = [Factor(name=f"f{i}", variants=[_variant("plays", 0.5), _variant("misses", 0.5)]) for i in range(6)]
    with pytest.raises(MixtureSizeError):
        scenario_mixture(factors=wide)

    with pytest.raises(ValueError):
        scenario_mixture(None)
