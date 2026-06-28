from __future__ import annotations

from itertools import combinations

from wolves.config import Settings
from wolves.sim.format import GROUPS, load_format

FMT = load_format(Settings().data_dir)
SLOT_ELIG = {m.match: set(m.away.removeprefix("3:")) for m in FMT.knockout if m.away.startswith("3:")}


def test_every_combination_resolves_to_an_eligible_permutation():
    for combo in combinations(range(12), 8):
        qualified = frozenset(combo)
        assignment = FMT.third_allocation(qualified)
        assert set(assignment) == set(SLOT_ELIG)
        assert sorted(assignment.values()) == sorted(combo)
        for match, group in assignment.items():
            assert GROUPS[group] in SLOT_ELIG[match]


def test_realized_round_of_32_matches_the_official_bracket():
    """The eight thirds that qualified (B, D, E, F, I, J, K, L) land exactly where
    FIFA's Annex C and the published fixtures put them."""
    qualified = frozenset(GROUPS.index(g) for g in "BDEFIJKL")
    assignment = {match: GROUPS[group] for match, group in FMT.third_allocation(qualified).items()}
    assert assignment == {74: "D", 77: "F", 79: "E", 80: "K", 81: "B", 82: "I", 85: "J", 87: "L"}
