"""Near-duplicate worlds that split a directional vote are flagged for merge;
genuinely opposing or distinct worlds are not."""

from __future__ import annotations

import pytest

from wolves.agent.mixture_hygiene import diluted_groups, world_signature


def _strength(team: str, mean: float) -> dict:
    return {"type": "StrengthPerturbation", "team": team, "delta": {"mean": mean, "sd": 0.04}}


def test_two_same_direction_spain_worlds_share_a_signature():
    a = world_signature([_strength("spain", 0.09)])
    b = world_signature([_strength("spain", 0.05)])
    assert a == b


def test_opposing_spain_worlds_do_not_share_a_signature():
    up = world_signature([_strength("spain", 0.09)])
    down = world_signature([_strength("spain", -0.09)])
    assert up != down


@pytest.mark.parametrize(
    ("worlds", "expected"),
    [
        # Split optimistic vote above the threshold: flagged.
        (
            {
                "spain_returns": (0.3, [_strength("spain", 0.09)]),
                "spain_depth": (0.3, [_strength("spain", 0.06)]),
                "spain_doubt": (0.4, [_strength("spain", -0.08)]),
            },
            [(["spain_depth", "spain_returns"], 0.6)],
        ),
        # Stories on different teams never collide.
        (
            {
                "spain": (0.5, [_strength("spain", 0.09)]),
                "france": (0.5, [_strength("france", 0.09)]),
            },
            [],
        ),
        # A duplicated pair below the combined-weight floor stays quiet.
        (
            {
                "spain_a": (0.05, [_strength("spain", 0.09)]),
                "spain_b": (0.05, [_strength("spain", 0.07)]),
                "base": (0.9, []),
            },
            [],
        ),
    ],
)
def test_diluted_groups(worlds, expected):
    assert diluted_groups(worlds, min_combined_weight=0.25) == expected
