from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from wolves.quant.wolves_quant import _insights, _sim
from wolves.quant.wolves_quant._state import SandboxContextError


def _forecaster() -> SimpleNamespace:
    teams = [SimpleNamespace(id="england"), SimpleNamespace(id="france")]
    state = SimpleNamespace(teams=["england", "france", "abkhazia"], strengths=[1.2, 1.1, 2.0])
    return SimpleNamespace(fmt=SimpleNamespace(teams=teams), state=state)


def test_title_uncertainty_defaults_to_tournament_teams(monkeypatch):
    monkeypatch.setattr(_sim, "forecaster", _forecaster)
    monkeypatch.setattr(
        _sim,
        "posterior_draws",
        lambda *_args, **_kwargs: pd.DataFrame(
            [{"england": 1.21, "france": 1.09, "abkhazia": 2.1}, {"england": 1.19, "france": 1.11, "abkhazia": 1.9}]
        ),
    )
    monkeypatch.setattr(_sim, "simulate", lambda *_args, **_kwargs: {"england": 0.12, "france": 0.1})

    table = _sim.title_uncertainty(n_draws=2)

    assert set(table.index) == {"england", "france"}
    assert set(table["team"]) == {"england", "france"}


def test_title_uncertainty_rejects_non_tournament_team(monkeypatch):
    monkeypatch.setattr(_sim, "forecaster", _forecaster)

    with pytest.raises(SandboxContextError, match="abkhazia"):
        _sim.title_uncertainty(teams=["abkhazia"])


def test_impact_can_include_named_team_outside_top_movers(monkeypatch):
    monkeypatch.setattr(_sim, "forecaster", _forecaster)
    monkeypatch.setattr(_sim, "baseline", lambda **_kwargs: {"england": 0.1, "france": 0.2})
    monkeypatch.setattr(_sim, "simulate", lambda *_args, **_kwargs: {"england": 0.101, "france": 0.25})
    monkeypatch.setattr(_sim, "noise_floor", lambda **_kwargs: 0.1)

    result = _sim.impact(object(), movers=1, include_teams=["england"])

    assert result["deltas_pp"] == {"france": 5.0, "england": 0.1}


def test_path_difficulty_defaults_to_tournament_teams(monkeypatch):
    monkeypatch.setattr(_sim, "forecaster", _forecaster)
    monkeypatch.setattr(_insights, "forecaster", _forecaster)
    monkeypatch.setattr(_insights, "context", lambda: SimpleNamespace(default_n_sims=100))

    calls: list[str] = []

    def fake_tree(_forecaster, team, **_kwargs):
        calls.append(team)
        stage = SimpleNamespace(
            stage="r32",
            p_play=1.0,
            slots=[SimpleNamespace(p_slot=1.0, opponents=[SimpleNamespace(team="france", p_opponent_given_slot=1.0)])],
        )
        return SimpleNamespace(stages=[stage])

    monkeypatch.setattr("wolves.insights.path_tree.team_path_tree", fake_tree)

    table = _insights.path_difficulty()

    assert set(calls) == {"england", "france"}
    assert set(table.index) == {"england", "france"}
    assert set(table["team"]) == {"england", "france"}


@pytest.mark.parametrize(
    ("helper", "args"),
    [
        (_sim.match_probs, ("england", "abkhazia")),
        (_sim.score_grid, ("england", "abkhazia")),
        (_sim.implied_delta, ("abkhazia", 0.2)),
        (_sim.update_from_result, ("england", "abkhazia", "win")),
        (_insights.model_explain, ("abkhazia",)),
        (_insights.path_tree, ("abkhazia",)),
    ],
)
def test_team_helpers_reject_non_tournament_ids(monkeypatch, helper, args):
    monkeypatch.setattr(_sim, "forecaster", _forecaster)
    monkeypatch.setattr(_insights, "forecaster", _forecaster)

    with pytest.raises(SandboxContextError, match="abkhazia"):
        helper(*args)
