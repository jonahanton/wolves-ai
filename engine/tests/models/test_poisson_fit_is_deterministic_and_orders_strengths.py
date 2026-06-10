from __future__ import annotations

from datetime import date

import numpy as np

from wolves.models.poisson import PoissonDecayModel


def test_fit_recovers_the_strength_ordering_and_repeats_exactly(fixture_dataset) -> None:
    model = PoissonDecayModel()
    state = model.fit(fixture_dataset, as_of=date(2026, 1, 1))

    by_team = dict(zip(state.teams, state.strengths, strict=True))
    assert by_team["alpha"] > by_team["beta"] > by_team["gamma"] > by_team["delta"]
    assert abs(float(state.strengths.mean())) < 1e-3
    assert state.globals_["home_adv"] > 0.0

    again = model.fit(fixture_dataset, as_of=date(2026, 1, 1))
    assert np.array_equal(state.strengths, again.strengths)
