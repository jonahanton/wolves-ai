from __future__ import annotations

import pytest

from wolves.forecast import MatchRatePerturbation, StrengthPerturbation
from wolves.quant.wolves_quant._sim import _validate_quant_perturbations


def test_quant_workbench_rejects_managed_load_as_global_strength() -> None:
    perturbation = StrengthPerturbation(
        team="england",
        delta=-0.04,
        reason="Saka Achilles load management",
    )

    with pytest.raises(ValueError, match="managed-load availability"):
        _validate_quant_perturbations((perturbation,))


def test_quant_workbench_allows_fixture_scoped_managed_load() -> None:
    perturbation = MatchRatePerturbation(
        match=1,
        home_goals_delta=-0.04,
        reason="Saka Achilles load management for one fixture",
    )

    _validate_quant_perturbations((perturbation,))
