from __future__ import annotations

from types import SimpleNamespace

import numpy as np

import wolves.forecast as forecast_module
from wolves.config import Settings
from wolves.forecast import Forecaster
from wolves.sim.format import PlayedResult


def test_default_played_results_are_passed_to_tournament_simulation(tmp_path, monkeypatch):
    forecaster = Forecaster(Settings(_env_file=None, runs_root=tmp_path, storage_mode="local"))
    played = {1: PlayedResult(match=1, home_goals=9, away_goals=0)}
    captured = {}

    monkeypatch.setattr(
        forecaster,
        "_perturbed",
        lambda perturbations: (SimpleNamespace(covariance=None), {}, {}, np.zeros(1)),
    )
    monkeypatch.setattr(forecast_module, "PoissonMatchEngine", lambda *args, **kwargs: object())

    def fake_run_tournament(*args, **kwargs):
        captured["results"] = kwargs["results"]
        return "sim-result"

    monkeypatch.setattr(forecast_module, "run_tournament", fake_run_tournament)
    forecaster.set_default_results(played)

    assert forecaster.simulate(n_sims=200, seed=7) == "sim-result"
    assert captured["results"] == played
