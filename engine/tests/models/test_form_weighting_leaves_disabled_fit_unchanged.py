from __future__ import annotations

from datetime import date

import numpy as np

from wolves.models.poisson import PoissonDecayModel, _blended_decay


def test_disabled_form_reproduces_the_single_decay_fit_exactly(fixture_dataset) -> None:
    baseline = PoissonDecayModel().fit(fixture_dataset, as_of=date(2026, 1, 1))
    off = PoissonDecayModel(form_half_life_days=120.0, form_weight=0.0).fit(fixture_dataset, as_of=date(2026, 1, 1))
    null_half_life = PoissonDecayModel(form_half_life_days=0.0, form_weight=0.5).fit(
        fixture_dataset, as_of=date(2026, 1, 1)
    )

    assert np.array_equal(baseline.strengths, off.strengths)
    assert np.array_equal(baseline.strengths, null_half_life.strengths)


def test_form_weighting_lifts_recent_matches_relative_to_old_ones() -> None:
    age = np.array([30.0, 1500.0])
    slow = _blended_decay(age, half_life_days=900.0, form_half_life_days=90.0, form_weight=0.0)
    blended = _blended_decay(age, half_life_days=900.0, form_half_life_days=90.0, form_weight=0.5)

    fast, slow_only = 0.5 ** (age / 90.0), 0.5 ** (age / 900.0)
    assert np.all(blended >= np.minimum(fast, slow_only) - 1e-12)
    assert np.all(blended <= np.maximum(fast, slow_only) + 1e-12)
    # The faster decay tilts weight toward the recent match relative to the old one.
    assert blended[0] / blended[1] > slow[0] / slow[1]
