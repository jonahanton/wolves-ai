from __future__ import annotations

import numpy as np
import pytest

from wolves.models.live_signals import DEFAULT_BLEND, BlendParams, LiveSignals, blend_rates


def test_shot_dominance_lifts_one_side_and_damps_the_other() -> None:
    signals = LiveSignals(home_shots_on=8, away_shots_on=1)
    home, away = blend_rates(1.3, 1.3, signals, 60.0)
    assert home > 1.3 > away


def test_blend_is_a_no_op_before_kickoff_or_without_signals() -> None:
    signals = LiveSignals(home_shots_on=5, away_shots_on=2)
    assert blend_rates(1.3, 1.1, signals, 0.0) == (1.3, 1.1)
    assert blend_rates(1.3, 1.1, LiveSignals(), 60.0) == (1.3, 1.1)


def test_multiplier_cap_bounds_a_runaway_early_shot_count() -> None:
    signals = LiveSignals(home_shots_on=12, away_shots_on=0, home_possession=0.9, away_possession=0.1)
    home, _ = blend_rates(2.0, 1.0, signals, 10.0)
    assert home <= 2.0 * DEFAULT_BLEND.multiplier_cap + 1e-9


def test_confidence_weight_rises_with_the_clock() -> None:
    """A fixed live pace earns more weight later in the match. Possession isolates
    this cleanly, since its tilt is linear in the weight and never hits the cap."""
    signals = LiveSignals(home_possession=0.7, away_possession=0.3)
    early, _ = blend_rates(1.3, 1.3, signals, 15.0)
    late, _ = blend_rates(1.3, 1.3, signals, 80.0)
    assert late > early > 1.3


def test_blend_broadcasts_over_per_draw_arrays() -> None:
    signals = LiveSignals(home_shots_on=7, away_shots_on=2)
    lam_home = np.array([1.1, 1.3, 1.5])
    lam_away = np.array([1.2, 1.0, 1.4])
    home, away = blend_rates(lam_home, lam_away, signals, 60.0)
    assert np.all(home > lam_home)
    assert np.all(away < lam_away)


def test_possession_alone_only_tilts_within_its_bound() -> None:
    signals = LiveSignals(home_possession=0.7, away_possession=0.3)
    params = BlendParams(possession_tilt=0.10)
    weight = 60.0 / (60.0 + params.halflife_minutes)
    home, away = blend_rates(1.3, 1.3, signals, 60.0, params=params)
    assert home == pytest.approx(1.3 * (1.0 + weight * params.possession_tilt * 0.4), rel=1e-6)
    assert away < 1.3
