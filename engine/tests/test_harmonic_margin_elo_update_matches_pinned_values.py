from __future__ import annotations

import numpy as np
import pytest

from wolves.sim.elo import expected_score, harmonic_margin, rating_delta


def test_margin_multiplier_is_harmonic():
    np.testing.assert_allclose(
        harmonic_margin(np.array([0, 1, 2, 3, 4])),
        [1.0, 1.0, 1.5, 1.5 + 1 / 3, 1.5 + 1 / 3 + 0.25],
    )


def test_group_stage_two_goal_win_delta_is_pinned():
    diff = np.array([100.0])
    expected = 1.0 / (1.0 + 10.0**-0.25)
    delta = rating_delta(diff, np.array([3]), np.array([1]), stage="group")
    assert delta[0] == pytest.approx(32.0 * 1.6 * 1.5 * (1.0 - expected))
    assert delta[0] == pytest.approx(27.643, abs=1e-3)


def test_knockout_draw_delta_uses_elevated_k():
    diff = np.array([100.0])
    delta = rating_delta(diff, np.array([1]), np.array([1]), stage="knockout")
    assert delta[0] == pytest.approx(32.0 * 1.76 * (0.5 - float(expected_score(diff)[0])))
    assert delta[0] == pytest.approx(-7.888, abs=1e-3)
