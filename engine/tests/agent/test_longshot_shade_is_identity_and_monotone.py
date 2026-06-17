"""longshot_shade with alpha=0 must leave the distribution untouched; alpha>0
must shrink longshots more than favourites and renormalise to a partition."""

from __future__ import annotations

from wolves.agent.consensus import longshot_shade

_TITLES = {"spain": 0.18, "france": 0.13, "england": 0.09, "tail": 0.60}


def test_alpha_zero_is_identity():
    assert longshot_shade(_TITLES, alpha=0.0) == _TITLES


def test_positive_alpha_renormalises_and_shades_longshots_down():
    shaded = longshot_shade(_TITLES, alpha=0.3)

    assert abs(sum(shaded.values()) - 1.0) < 1e-9
    # The smallest probability is the longest shot and must fall, relatively,
    # while the order is preserved (monotone in the input).
    ranked_in = sorted(_TITLES, key=lambda t: _TITLES[t])
    ranked_out = sorted(shaded, key=lambda t: shaded[t])
    assert ranked_in == ranked_out
    assert shaded["england"] < _TITLES["england"]
